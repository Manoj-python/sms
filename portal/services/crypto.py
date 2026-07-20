"""Column-level encryption helpers (Fernet) + PII masking utilities."""

import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet
from django.db import models

from portal.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key or key == "change-me":
        # Deterministic dev-only key so the app boots without a real .env;
        # a real ENCRYPTION_KEY is mandatory outside local development.
        import base64

        key = base64.urlsafe_b64encode(hashlib.sha256(b"dev-only").digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedCharField(models.CharField):
    """Transparently encrypts a string column at rest (Fernet)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 512)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None:
            return None
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return _fernet().decrypt(value.encode()).decode()


def sha256_hex(value: str) -> str:
    """Deterministic hash for lookups (e.g. otp_log keyed by mobile) so the
    plaintext mobile never needs to be stored or indexed."""
    return hashlib.sha256(value.encode()).hexdigest()


def mask_mobile(mobile: str) -> str:
    digits = "".join(ch for ch in mobile if ch.isdigit())
    if len(digits) < 4:
        return "*" * len(digits)
    return "X" * (len(digits) - 4) + digits[-4:]
