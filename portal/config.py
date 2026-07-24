"""Central configuration via pydantic-settings.

All credentials come from the environment (.env). UAT and prod credential
sets are kept separate; `APP_ENV` selects which set the properties expose.

This is deliberately kept as a standalone pydantic-settings object (same as
the original FastAPI portal) rather than folded into Django's own
settings.py — the AllCloud/SMS/business config below has nothing to do with
Django's request/response machinery, and every service module below imports
`get_settings()` exactly as it always did.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "uat"  # uat | prod
    secret_key: str = "dev-only-not-secret"
    encryption_key: str = ""
    database_url: str = "mysql+pymysql://portal:portal@localhost:3306/smsquare_portal"

    # --- AllCloud LMS (UAT: dynamic per-call signing, unverified against
    # real AllCloud) ---
    lms_mock: bool = True
    lms_base_url_uat: str = "https://uat-apiv2-smsquare.allcloud.app"
    allcloud_auth_url: str = (
        "https://prod-auth-ace.allcloud.app/enterprise-generatetoken"
    )

    allcloud_appid_uat: str = ""
    allcloud_secret_uat: str = ""
    allcloud_usertoken_uat: str = ""
    allcloud_apikey_uat: str = ""

    lms_timeout_seconds: float = 70.0
    lms_max_retries: int = 2
    # Bounded timeout for the multi-tenant "which lender is this" discovery
    # probes (multi_lms.py) — every real hit/miss has resolved in well under
    # 1.5s in testing, so a tenant that's genuinely hanging (not just
    # erroring) shouldn't be able to stall a login/dashboard load by the
    # full lms_timeout_seconds. Every other call keeps the 10s default.
    lms_discovery_timeout_seconds: float = 4.0

    # --- AllCloud LMS (prod: static pre-issued `amx` tokens, no per-call
    # signing) --------------------------------------------------------------
    # AllCloud serves SMSquare across TWO hosts in production, each with its
    # own long-lived token:
    #   - lookups (GetCustomerSearch, GetLoanByMobileNumber,
    #     GetLoanAgreementNoAsync, GetRepaymentForLoanByLoanId) -> apiv2 host
    #   - payment gateway (GetQRCode) -> "api" host; the apiv2 host 401s here
    # saverepayment is deliberately NOT called (its host is unconfirmed).
    # See payment_service.py for the reconciliation model.
    lms_lookup_base_url_prod: str = "https://prod-apiv2-smsquare.allcloud.app"
    lms_payment_base_url_prod: str = "https://prod-api-smsquare.allcloud.app"

    # Same env var names as the FastAPI portal / reference scripts, so the
    # same secret values can be reused as-is.
    apiv2_auth_smsquare: str = ""
    pg_api_auth_smsquare: str = ""
    # LCC (Loan Collection) voicecall details — same "api" host as the
    # payment gateway, separate static token.
    lcc_api_auth_smsquare: str = ""

    # --- AllCloud LMS: acquired portfolios (Padmasai, Sreemani) ------------
    # SMSquare purchased loan books originally on these two lenders' own
    # AllCloud tenants — customers from either now log into THIS portal too
    # (seamless: they never pick a lender). Only ONE static token per tenant
    # was issued (reused across lookup + LCC calls — same token, confirmed
    # live 2026-07-21 by probing both). BUT unlike the token, the HOST
    # splits the same way SMSquare's does: lookups (GetCustomerSearch,
    # GetLoanByMobileNumber, GetLoanAgreementNoAsync) live on the apiv2 host;
    # GetLccDetailsByAgreementNo 404s there and needs the non-"v2" host
    # instead (confirmed live — apiv2 gave 404, prod-api gave 200 with real
    # data for both tenants). Payment/GetQRCode host is UNCONFIRMED for
    # these two (not smoke-tested — no live payment call was made) —
    # currently assumed to be the apiv2 host same as lookups; verify with a
    # real (or deliberately tiny) GetQRCode call before trusting this in
    # production. Prod-only — no UAT/dynamic-signing story exists for these.
    lms_apiv2_base_url_padmasai: str = "https://prod-apiv2-padmasai.allcloud.app"
    lms_lcc_base_url_padmasai: str = "https://prod-api-padmasai.allcloud.app"
    apiv2_auth_padmasai: str = ""
    # Sreemani has no AllCloud host of its own — reuses Padmasai's for both
    # apiv2 and LCC hosts, per the acquisition (confirmed live 2026-07-21:
    # Sreemani's own token works correctly against Padmasai's hosts and
    # returns Sreemani's own distinct customer/loan data, not Padmasai's).
    lms_apiv2_base_url_sreemani: str = "https://prod-apiv2-padmasai.allcloud.app"
    lms_lcc_base_url_sreemani: str = "https://prod-api-padmasai.allcloud.app"
    apiv2_auth_sreemani: str = ""

    # AllCloud enum value for GetQRCode's CollectionType (generic "collection").
    lms_collection_type_default: int = 5

    # --- Portal behaviour ---
    session_idle_minutes: int = 240  # 4 hours
    # How often dashboard() re-checks ALL 3 AllCloud tenants (vs. just the
    # ones already known from a session's finance_lenders) for a mobile's
    # loans — a full scan costs 2 guaranteed-empty extra calls for any
    # customer who only holds loans at one lender (the common case), so
    # it's only worth paying on every single page view if catching a
    # brand-new loan at a different lender within this window matters more
    # than the extra AllCloud load. See dashboard.py.
    full_lender_rescan_minutes: int = 30
    otp_expiry_minutes: int = 5  # must match the DLT-registered SMS template's "valid only for 5 mins"
    otp_max_attempts: int = 3
    otp_resend_seconds: int = 30
    otp_hourly_limit: int = 5
    min_part_payment: int = 100

    # --- PIN quick-unlock (opt-in device trust — see device_trust_service.py) ---
    device_trust_days: int = 90
    pin_max_attempts: int = 5
    pin_lockout_minutes: int = 30

    admin_probe_key: str = ""

    # --- PhonePe Payment Gateway (alternative to AllCloud's GetQRCode) -----
    # Built and verified against real production PhonePe (see
    # phonepe_client.py), but deliberately kept OFF for this go-live —
    # parked for a future release rather than shipped now. Customers never
    # see the button and the routes 404 while this is False; nothing else
    # about the integration needs to change to turn it on later.
    phonepe_enabled: bool = False
    # The merchant account only has v1 (checksum/salt-key) API access
    # enabled, not v2/Standard Checkout's OAuth-based Client ID/Secret — so
    # this integration hand-rolls the v1 X-VERIFY checksum signing rather
    # than using PhonePe's v2-only official SDK (see phonepe_client.py).
    #
    # phonepe_use_production is a DELIBERATE separate switch from is_prod:
    # real production merchant credentials are already in hand, but the
    # hand-rolled checksum/request-signing code needs to be verified end to
    # end against PhonePe's sandbox first — flip this only after that.
    # PGTESTPAYUAT below is PhonePe's own PUBLIC sandbox merchant (same
    # value published in PhonePe's own old docs/tutorials), safe as a
    # checked-in default. The *_prod fields have no default — they must
    # only ever come from the real .env, never be hardcoded here.
    phonepe_use_production: bool = False
    phonepe_merchant_id: str = "PGTESTPAYUAT"
    phonepe_salt_key: str = "099eb0cd-02cf-4e2a-8aca-3e6c6aff0399"
    phonepe_salt_index: int = 1
    phonepe_host_url_sandbox: str = "https://api-preprod.phonepe.com/apis/pg-sandbox"

    phonepe_merchant_id_prod: str = ""
    phonepe_salt_key_prod: str = ""
    phonepe_salt_index_prod: int = 1
    phonepe_host_url_prod: str = "https://api.phonepe.com/apis/hermes"

    # --- SMS gateway (SmsCountry) --- OTP delivery. Confirmed request shape:
    # GET SMSCwebservice_bulk.aspx with querystring keys User/passwd/
    # mobilenumber/message/sid/mtype/DR. Leave smscountry_user blank to fall
    # back to logging the OTP to the console (UAT convenience).
    smscountry_url: str = "https://api.smscountry.com/SMSCwebservice_bulk.aspx"
    smscountry_user: str = ""
    smscountry_password: str = ""
    smscountry_sid: str = ""
    # Brand name closing the DLT template — must match whichever account
    # (smscountry_user/sid) is actually sending, since DLT templates are
    # registered per entity.
    smscountry_brand_name: str = "SMSQUARE"

    legal_name: str = "SMSquare Credit Services Pvt Ltd."
    company_address: str = (
        "14th Floor, T 19 Towers, Ranigunj, Secunderabad, Hyderabad. Telangana - 500003"
    )
    grievance_officer: str = "Grievance Officer, SMSquare Credit Services"
    grievance_email: str = "support@smsquare.info"
    grievance_phone: str = "+91-00000-00000"
    ombudsman_url: str = "https://cms.rbi.org.in"
    # Same number for calls and WhatsApp.
    helpline_number: str = "8333000111"
    # Public base URL this portal is reachable at — used only to build the
    # verification QR code URL embedded in downloaded PDFs (see doc_verify.py).
    # Defaults to localhost for local dev; must be set to the real deployed
    # domain in prod or the QR codes won't resolve for anyone else.
    portal_base_url: str = "http://localhost:8001"

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "prod"

    # --- PhonePe v1 credential resolution (see phonepe_use_production above) ---
    @property
    def phonepe_active_merchant_id(self) -> str:
        return self.phonepe_merchant_id_prod if self.phonepe_use_production else self.phonepe_merchant_id

    @property
    def phonepe_active_salt_key(self) -> str:
        return self.phonepe_salt_key_prod if self.phonepe_use_production else self.phonepe_salt_key

    @property
    def phonepe_active_salt_index(self) -> int:
        return self.phonepe_salt_index_prod if self.phonepe_use_production else self.phonepe_salt_index

    @property
    def phonepe_active_host_url(self) -> str:
        return self.phonepe_host_url_prod if self.phonepe_use_production else self.phonepe_host_url_sandbox

    # UAT-only: dynamic per-call signing credentials (unverified).
    @property
    def allcloud_appid(self) -> str:
        return self.allcloud_appid_uat

    @property
    def allcloud_secret(self) -> str:
        return self.allcloud_secret_uat

    @property
    def allcloud_usertoken(self) -> str:
        return self.allcloud_usertoken_uat

    @property
    def allcloud_apikey(self) -> str:
        return self.allcloud_apikey_uat

    # --- per-call-kind host + static-token resolution ---------------------
    @property
    def lookup_base_url(self) -> str:
        return self.lms_lookup_base_url_prod if self.is_prod else self.lms_base_url_uat

    @property
    def payment_base_url(self) -> str:
        return self.lms_payment_base_url_prod if self.is_prod else self.lms_base_url_uat

    @property
    def lookup_auth_header(self) -> str | None:
        return self.apiv2_auth_smsquare if self.is_prod else None

    @property
    def payment_auth_header(self) -> str | None:
        return self.pg_api_auth_smsquare if self.is_prod else None

    @property
    def lcc_auth_header(self) -> str | None:
        return self.lcc_api_auth_smsquare if self.is_prod else None

    # --- acquired-portfolio tenant resolution ------------------------------
    # Keyed by an explicit lender string rather than overloading the
    # zero-arg properties above, which stay SMSquare-only and untouched.
    LENDER_KEYS: tuple[str, ...] = ("smsquare", "padmasai", "sreemani")

    def tenant_base_url(self, lender: str, *, lcc: bool = False) -> str:
        """`lcc=True` for GetLccDetailsByAgreementNo — confirmed live that it
        needs the non-"v2" host, unlike every other call kind for these two
        tenants (see the block comment above where these fields are defined)."""
        if lender == "padmasai":
            return self.lms_lcc_base_url_padmasai if lcc else self.lms_apiv2_base_url_padmasai
        if lender == "sreemani":
            return self.lms_lcc_base_url_sreemani if lcc else self.lms_apiv2_base_url_sreemani
        raise ValueError(f"tenant_base_url: unknown lender {lender!r}")

    def tenant_auth_header(self, lender: str) -> str | None:
        if not self.is_prod:
            return None  # Padmasai/Sreemani have no UAT story — mock mode never reaches here
        if lender == "padmasai":
            return self.apiv2_auth_padmasai
        if lender == "sreemani":
            return self.apiv2_auth_sreemani
        raise ValueError(f"tenant_auth_header: unknown lender {lender!r}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
