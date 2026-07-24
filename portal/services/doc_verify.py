"""Signs a small set of basic details into every downloaded PDF as a QR
code, so anyone (the customer, a bank, an RTO, a field agent) can scan it
and confirm the document matches what this portal actually issued —
without needing to log in or call anyone.

Stateless by design: the token is itsdangerous-signed (same mechanism as
session cookies — see session_service.py), not a database row. Verification
just re-checks the signature; there's nothing to look up, so no new table,
and nothing here is invalidated if the loan's live data changes later. A
tampered amount/date/loan-number in the token fails to verify.

Deliberately excludes anything sensitive: no full mobile number, no DOB,
no address — just loan number, document type, the headline amount, the
document's own date, and when it was generated.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from itsdangerous import BadSignature, URLSafeSerializer

from portal.config import get_settings

IST = timezone(timedelta(hours=5, minutes=30))

DOC_LABELS = {
    "statement": "Statement of Account",
    "foreclosure": "Foreclosure Statement",
    "receipt": "Payment Receipt",
    "charge_receipt": "Charge Receipt",
}


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="portal-doc-verify")


def sign_document(doc_type: str, agreement_no: str, amount: float, doc_date: str) -> str:
    payload = {
        "doc": doc_type,
        "agr": agreement_no,
        "amt": round(float(amount), 2),
        "date": doc_date,
        "gen": datetime.now(IST).strftime("%Y-%m-%d %H:%M"),
    }
    return _serializer().dumps(payload)


def verify_token(token: str) -> dict | None:
    try:
        return _serializer().loads(token)
    except BadSignature:
        return None


def verify_url(doc_type: str, agreement_no: str, amount: float, doc_date: str) -> str:
    token = sign_document(doc_type, agreement_no, amount, doc_date)
    base = get_settings().portal_base_url.rstrip("/") + "/"
    return urljoin(base, f"verify/{token}")
