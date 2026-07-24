"""DOB-based password protection for customer-facing PDFs (statement,
receipts) — the common convention on Indian bank/NBFC statements: the
document opens only with the account holder's date of birth, DDMMYYYY,
no separators."""

import datetime as dt
import re

from reportlab.lib.pdfencrypt import StandardEncryption

# Mirrors auth.py's _DOB_FORMATS — AllCloud's DOB format is unconfirmed, so
# parse actual dates rather than assume a single format.
_DOB_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y")


def dob_password(dob: str) -> str | None:
    """Returns DDMMYYYY for a valid DOB string, or None if it can't be
    parsed — callers should skip encryption rather than lock a customer out
    of their own document with a guessed password."""
    if not dob:
        return None
    head = re.split(r"[T ]", dob.strip(), maxsplit=1)[0]
    for fmt in _DOB_FORMATS:
        try:
            parsed = dt.datetime.strptime(head, fmt).date()
        except ValueError:
            continue
        return parsed.strftime("%d%m%Y")
    return None


def encryption_for(dob: str) -> StandardEncryption | None:
    """StandardEncryption for reportlab's canvas.Canvas(encrypt=...) /
    SimpleDocTemplate(encrypt=...). Printing is left enabled (a customer
    should be able to print their own statement); copy/modify/annotate are
    disabled since this is a formal financial document, not editable."""
    password = dob_password(dob)
    if not password:
        return None
    return StandardEncryption(
        userPassword=password,
        ownerPassword=password,
        canPrint=1,
        canModify=0,
        canCopy=0,
        canAnnotate=0,
    )
