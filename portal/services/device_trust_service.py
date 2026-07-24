"""Opt-in "remember this device" PIN quick-unlock — a convenience layer on
top of a real OTP/agreement+DOB login, never a replacement for one. A
DeviceTrust row only means anything paired with the matching signed cookie
on the exact browser that created it (see set_device_cookie/load_device);
the PIN itself never re-proves identity from scratch — verifying it just
lets auth.pin_unlock re-run the same session-creation flow a fresh OTP
login would (see auth._finish_login).

Mirrors session_service.py's shape closely (own cookie name, own
itsdangerous signing salt, same load/verify/revoke pattern) — deliberately
NOT the same cookie or signing salt as the session cookie, since a device
trust and a live session are different, independently-lived things (a
device trust outlives many session expiries)."""

from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from itsdangerous import BadSignature, URLSafeSerializer

from portal.config import get_settings
from portal.models import DeviceTrust
from portal.services.crypto import mask_mobile

COOKIE_NAME = "smsq_device"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="portal-device")


async def create(mobile: str, pin: str) -> DeviceTrust:
    """Caller (auth.pin_setup) is responsible for validating `pin` is
    exactly 6 digits before calling this — this layer only hashes and
    stores it."""
    return await DeviceTrust.objects.acreate(
        mobile=mobile,
        mobile_mask=mask_mobile(mobile),
        pin_hash=make_password(pin),
    )


def set_device_cookie(response: HttpResponse, device_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _serializer().dumps(device_id),
        httponly=True,
        secure=get_settings().is_prod,
        samesite="Lax",
        max_age=get_settings().device_trust_days * 24 * 3600,
    )


def clear_device_cookie(response: HttpResponse) -> None:
    response.delete_cookie(COOKIE_NAME)


async def load_device(request: HttpRequest) -> DeviceTrust | None:
    """Returns the live, non-revoked, non-locked DeviceTrust or None —
    missing cookie, bad signature, revoked, and currently-locked-out (see
    verify_pin) are all treated identically as "no usable device trust",
    which auth.login_page falls back to the normal mobile+OTP form for."""
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        device_id = _serializer().loads(raw)
    except BadSignature:
        return None
    device = await DeviceTrust.objects.filter(pk=device_id).afirst()
    if device is None or device.revoked:
        return None
    if device.locked_until and timezone.now() < device.locked_until:
        return None
    return device


async def verify_pin(device: DeviceTrust, pin: str) -> bool:
    """On failure, increments failed_attempts and locks the device once it
    hits pin_max_attempts — the caller must fall back to a full OTP login
    to unlock again (see auth.login_page's locked-device branch); this
    layer never auto-clears a lockout early. On success, resets the
    counter and bumps last_used_at."""
    s = get_settings()
    if not check_password(pin, device.pin_hash):
        device.failed_attempts += 1
        if device.failed_attempts >= s.pin_max_attempts:
            device.locked_until = timezone.now() + timedelta(minutes=s.pin_lockout_minutes)
        await device.asave()
        return False
    device.failed_attempts = 0
    device.locked_until = None
    device.last_used_at = timezone.now()
    await device.asave()
    return True


async def revoke(device: DeviceTrust) -> None:
    device.revoked = True
    await device.asave()
