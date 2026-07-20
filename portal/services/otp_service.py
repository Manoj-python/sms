"""OTP lifecycle: 6-digit, 5-min expiry (matches the DLT-registered SMS
template), 3 attempts, 30s resend gap, 5/hour per-mobile limit (DB-enforced).
OTPs and mobiles are stored only as SHA-256 hashes."""

import logging
import secrets
from datetime import timedelta

import httpx
from django.utils import timezone

from portal.config import get_settings
from portal.models import OtpLog
from portal.services.crypto import mask_mobile, sha256_hex

logger = logging.getLogger("otp")


class OtpError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code  # i18n key, e.g. "otp_rate_limited"


def _hash_otp(mobile: str, otp: str) -> str:
    return sha256_hex(f"{mobile}:{otp}")


async def send_otp(mobile: str) -> None:
    s = get_settings()
    mhash = sha256_hex(mobile)
    now = timezone.now()

    sent_last_hour = await OtpLog.objects.filter(
        mobile_hash=mhash, created_at__gte=now - timedelta(hours=1)
    ).acount()
    if sent_last_hour >= s.otp_hourly_limit:
        raise OtpError("otp_rate_limited")

    latest = await OtpLog.objects.filter(mobile_hash=mhash).order_by("-created_at").afirst()
    if latest and (now - latest.created_at).total_seconds() < s.otp_resend_seconds:
        raise OtpError("otp_resend_wait")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    await OtpLog.objects.acreate(
        mobile_hash=mhash,
        mobile_mask=mask_mobile(mobile),
        otp_hash=_hash_otp(mobile, otp),
        expires_at=now + timedelta(minutes=s.otp_expiry_minutes),
    )
    await _deliver_sms(mobile, otp)


async def _deliver_sms(mobile: str, otp: str) -> None:
    """Sends the OTP via SmsCountry's bulk API (SMSCwebservice_bulk.aspx):
    GET with querystring params User/passwd/mobilenumber/message/sid/mtype/DR
    — one message per call."""
    s = get_settings()
    # DLT-registered template — do not reword; a mismatch gets the SMS
    # silently blocked by the carrier, not just garbled. The brand name at
    # the end must match whichever SmsCountry account (smscountry_user/sid)
    # is actually configured — DLT templates are registered per entity.
    message = (
        f"Dear Customer, One Time Password(OTP) is {otp} to complete your "
        f"mobile verification. This is valid only for 5 mins. {s.smscountry_brand_name}."
    )
    if not s.smscountry_user:
        # UAT convenience: no gateway configured -> console. Masked number only.
        logger.warning("SMS stub -> %s : OTP %s", mask_mobile(mobile), otp)
        return
    params = {
        "User": s.smscountry_user,
        "passwd": s.smscountry_password,
        "mobilenumber": mobile,
        "message": message,
        "sid": s.smscountry_sid,
        "mtype": "N",
        "DR": "Y",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(s.smscountry_url, params=params)
    # HTTP 200 only means "gateway accepted the request" — SmsCountry reports
    # actual delivery/rejection (DLT scrubbing, bad sid, etc.) in the body.
    # Redact the OTP itself before logging in case it's echoed back.
    safe_body = resp.text.replace(otp, "***").strip()[:300]
    logger.info(
        "SmsCountry -> %s : http_status=%s body=%s",
        mask_mobile(mobile), resp.status_code, safe_body,
    )


async def verify_otp(mobile: str, otp: str) -> bool:
    """Validates against the latest unverified OTP. Raises OtpError with an
    i18n code on expiry/attempt-exhaustion; returns False on plain mismatch."""
    s = get_settings()
    mhash = sha256_hex(mobile)
    row = await OtpLog.objects.filter(
        mobile_hash=mhash, verified=False
    ).order_by("-created_at").afirst()
    if row is None:
        raise OtpError("otp_not_found")
    if timezone.now() > row.expires_at:
        raise OtpError("otp_expired")
    if row.attempts >= s.otp_max_attempts:
        raise OtpError("otp_attempts_exhausted")

    row.attempts += 1
    if secrets.compare_digest(row.otp_hash, _hash_otp(mobile, otp)):
        row.verified = True
        await row.asave()
        return True
    await row.asave()
    if row.attempts >= s.otp_max_attempts:
        raise OtpError("otp_attempts_exhausted")
    return False
