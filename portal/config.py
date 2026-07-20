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

    # AllCloud enum value for GetQRCode's CollectionType (generic "collection").
    lms_collection_type_default: int = 5

    # --- Portal behaviour ---
    session_idle_minutes: int = 240  # 4 hours
    otp_expiry_minutes: int = 5  # must match the DLT-registered SMS template's "valid only for 5 mins"
    otp_max_attempts: int = 3
    otp_resend_seconds: int = 30
    otp_hourly_limit: int = 5
    min_part_payment: int = 100

    admin_probe_key: str = ""

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
