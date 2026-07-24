"""Portal-owned tables. No loan data here — AllCloud is the system of record.

Table names/columns match db/schema.sql exactly (ported 1:1 from the
FastAPI/SQLAlchemy version) so the same MySQL schema is usable.
"""

import uuid

from django.db import models
from django.utils import timezone

from portal.services.crypto import EncryptedCharField


def new_uuid() -> str:
    return uuid.uuid4().hex


class PortalSession(models.Model):
    id = models.CharField(max_length=32, primary_key=True, default=new_uuid)
    mobile = EncryptedCharField()  # encrypted at rest
    mobile_mask = models.CharField(max_length=20)  # safe for display/logs
    customer_name = models.CharField(max_length=120, default="", blank=True)
    # FinanceIds this verified mobile may access — refreshed from LMS; the
    # server-side IDOR check on every LMS proxy call reads this list.
    finance_ids = models.JSONField(default=list)
    # Maps each entry in finance_ids -> which AllCloud tenant it belongs to
    # ("smsquare" | "padmasai" | "sreemani") — a customer's loan may come
    # from any of SMSquare's own portfolio or the two acquired ones, and the
    # customer never selects/knows which; every per-loan view needs this to
    # route its LMS calls to the correct tenant. Kept in lockstep with
    # finance_ids by session_service.update_finance_ids. Missing/empty is
    # treated as "smsquare" by callers (the only tenant that existed before
    # this field did).
    finance_lenders = models.JSONField(default=dict)
    # Last time finance_ids/finance_lenders came from a FULL 3-tenant scan
    # (multi_lms.loans_by_mobile_all_tenants), vs. a cheaper re-check of only
    # the tenants already known from finance_lenders. None means "never
    # scanned yet" — forces a full scan on the next dashboard view. See
    # dashboard.py and config.py's full_lender_rescan_minutes.
    last_lender_scan_at = models.DateTimeField(null=True, blank=True)
    login_method = models.CharField(max_length=20, default="mobile_otp")
    created_at = models.DateTimeField(auto_now_add=True)
    # NOT auto_now — session_service.load_session bumps this on every
    # authenticated request to track the idle timeout, which auto_now/
    # auto_now_add would either ignore (add) or force on every unrelated
    # save (now).
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked = models.BooleanField(default=False)

    class Meta:
        db_table = "sessions"
        indexes = [models.Index(fields=["last_seen_at"], name="idx_sessions_last_seen")]


class OtpLog(models.Model):
    mobile_hash = models.CharField(max_length=64, db_index=True)
    mobile_mask = models.CharField(max_length=20)
    otp_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=30, default="login")
    attempts = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "otp_log"
        indexes = [models.Index(fields=["mobile_hash", "created_at"], name="idx_otp_mobile")]


class PgTransaction(models.Model):
    idempotency_key = models.CharField(max_length=32, unique=True, default=new_uuid)
    session_id = models.CharField(max_length=32, db_index=True)
    mobile = EncryptedCharField()
    finance_id = models.CharField(max_length=40, db_index=True)
    agreement_no = models.CharField(max_length=40, default="", blank=True)
    # Which AllCloud tenant this transaction's finance_id/GetQRCode call
    # belongs to ("smsquare" | "padmasai" | "sreemani") — needed since ops
    # reconciles lms_receipt_ref against that SPECIFIC tenant's own AllCloud
    # instance, not necessarily SMSquare's.
    lender = models.CharField(max_length=20, default="smsquare", blank=True)
    # Which payment gateway this transaction was created through — "allcloud"
    # (GetQRCode, optimistic success, ops reconciles manually) or "phonepe"
    # (real webhook/status-check confirmation, auto-reconciled — see
    # payment_service.confirm_phonepe_payment).
    gateway = models.CharField(max_length=20, default="allcloud")

    # component split shown to the customer (never posted to AllCloud — see
    # payment_service.py; saverepayment's host is unconfirmed and not called)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # principal/EMI portion
    lpi_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # penal charges (LPC)
    collection_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_option = models.CharField(max_length=20, default="total")  # total|emi|part

    # INITIATED -> QR_GENERATED -> GATEWAY_SUCCESS (terminal, automatic)
    # Ops reconciles GATEWAY_SUCCESS rows into AllCloud out-of-band and may
    # set status to RECONCILED directly in this table once posted.
    status = models.CharField(max_length=30, default="INITIATED", db_index=True)
    utr = models.CharField(max_length=60, default="", blank=True)
    receipt_no = models.CharField(max_length=40, default="", blank=True)
    lms_receipt_ref = models.CharField(max_length=80, default="", blank=True)  # ops fills in manually
    last_error = models.TextField(default="", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pg_transactions"


class LmsApiLog(models.Model):
    method = models.CharField(max_length=8)
    endpoint = models.CharField(max_length=255)  # path only, PII stripped
    status_code = models.IntegerField(null=True)
    latency_ms = models.IntegerField(default=0)
    ok = models.BooleanField(default=False)
    error = models.CharField(max_length=255, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "lms_api_log"


class AuditLog(models.Model):
    session_id = models.CharField(max_length=32, default="", blank=True, db_index=True)
    mobile_mask = models.CharField(max_length=20, default="", blank=True)
    # Full mobile number, encrypted at rest — shown unmasked on the internal
    # staff audit report per an explicit product decision (staff need to
    # identify/contact customers from this report). mobile_mask is kept
    # alongside for rows written before this field existed.
    mobile = EncryptedCharField(default="", blank=True)
    action = models.CharField(max_length=60, db_index=True)
    detail = models.TextField(default="", blank=True)
    ip = models.CharField(max_length=45, default="", blank=True)
    # City/region/country + coordinates resolved from `ip` — filled in
    # asynchronously after the row is created (see services/geoip.py) so a
    # third-party lookup never adds latency to the customer-facing request
    # that triggered the audit event. Blank until that background task
    # finishes, or permanently blank for private/local IPs.
    location = models.CharField(max_length=120, default="", blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_log"


class StaffUser(models.Model):
    """Internal staff account for the audit report — deliberately separate
    from customer PortalSessions/auth (different cookie, different login
    page, no OTP). No self-service signup: provisioned via the
    create_staff_user management command."""
    username = models.CharField(max_length=60, unique=True)
    password_hash = models.CharField(max_length=200)  # django.contrib.auth.hashers, no auth app needed
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_users"


class StaffSession(models.Model):
    id = models.CharField(max_length=32, primary_key=True, default=new_uuid)
    username = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked = models.BooleanField(default=False)

    class Meta:
        db_table = "staff_sessions"


class DeviceTrust(models.Model):
    """A customer's opt-in "remember this device" record for PIN quick-
    unlock (see device_trust_service.py) — deliberately NOT a login
    credential on its own: it only means anything paired with the matching
    signed device cookie set on the same browser that created it. The PIN
    never re-proves identity from scratch; it just re-establishes a normal
    PortalSession the same way a fresh OTP login would (same finance_ids
    derivation), skipping only the OTP step for a device that already
    completed one properly."""
    id = models.CharField(max_length=32, primary_key=True, default=new_uuid)
    mobile = EncryptedCharField()  # encrypted at rest, same as PortalSession.mobile
    mobile_mask = models.CharField(max_length=20)
    pin_hash = models.CharField(max_length=128)  # django.contrib.auth.hashers, same as StaffUser
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(default=timezone.now)
    revoked = models.BooleanField(default=False)

    class Meta:
        db_table = "device_trusts"


class BlockedLoan(models.Model):
    """Staff-managed deny-list — access to a SPECIFIC loan can be cut off
    without affecting any other loan the same customer holds (see
    decorators.assert_loan_access, which is the single enforcement point
    for every loan-scoped view). Independent of AllCloud's own loan status;
    this is purely an internal portal-access control, not a statement about
    the loan itself."""
    id = models.CharField(max_length=32, primary_key=True, default=new_uuid)
    finance_id = models.CharField(max_length=40, db_index=True)
    agreement_no = models.CharField(max_length=40, default="", blank=True, db_index=True)
    # finance_id is only unique WITHIN a tenant — two different AllCloud
    # tenants (smsquare/padmasai/sreemani) could coincidentally reuse the
    # same numeric id for unrelated loans, so every lookup here is keyed on
    # the (finance_id, lender) pair, never finance_id alone.
    lender = models.CharField(max_length=20, default="smsquare")
    customer_name = models.CharField(max_length=120, default="", blank=True)
    mobile = EncryptedCharField(default="", blank=True)  # encrypted at rest, same as PortalSession.mobile
    mobile_mask = models.CharField(max_length=20, default="", blank=True)
    branch = models.CharField(max_length=80, default="", blank=True)
    centre = models.CharField(max_length=80, default="", blank=True)
    rsp_name = models.CharField(max_length=80, default="", blank=True)  # Relationship/Recovery Sales Person
    reason = models.TextField(default="", blank=True)
    blocked_by = models.CharField(max_length=60, default="", blank=True)  # StaffUser.username who added it
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blocked_loans"
        constraints = [models.UniqueConstraint(fields=["finance_id", "lender"], name="uniq_blocked_loan")]
