"""Hand-rolled PhonePe v1 (checksum/salt-key) Payment Gateway client — the
alternative to AllCloud's GetQRCode (see payments.py's
generate_phonepe_order/phonepe_return/phonepe_webhook). The merchant
account only has v1 API access enabled (Merchant ID + salt key + salt
index, X-VERIFY SHA256 checksum signing) — NOT v2/Standard Checkout's
OAuth-based Client ID/Secret — so this talks to PhonePe's REST endpoints
directly rather than using PhonePe's official SDK (v2-only). Endpoint
paths, checksum construction, and payload shapes are PhonePe's long-stable
v1 contract (their own current docs redirect v1 pages to v2, but the API
itself is unchanged and still what this merchant account is provisioned
for) — cross-checked against a working community reference implementation
during development, not guessed from memory.

All amounts in this module are in PAISE (PhonePe's unit) except where a
function explicitly takes/returns rupees — the module boundary is where
the rupees->paise conversion happens, so callers elsewhere in the portal
never have to think about it.
"""

import base64
import hashlib
import json
import logging

import httpx

from portal.config import get_settings

logger = logging.getLogger("phonepe.client")

_TIMEOUT = httpx.Timeout(15.0)


class PhonePeError(Exception):
    """Mirrors LMSError's role for the AllCloud client — callers only need
    to catch this, not httpx's or json's own exceptions."""


def _checksum(signed_string: str) -> str:
    s = get_settings()
    digest = hashlib.sha256((signed_string + s.phonepe_active_salt_key).encode("utf-8")).hexdigest()
    return f"{digest}###{s.phonepe_active_salt_index}"


async def create_order(merchant_order_id: str, amount_rupees: float, redirect_url: str) -> tuple[str, str]:
    """Returns (checkout_redirect_url, merchant_order_id). merchant_order_id
    is the portal's own PgTransaction.idempotency_key, reused directly as
    PhonePe's merchantTransactionId — every later status check/webhook
    keys off it, so no second ID needs to be minted or stored."""
    s = get_settings()
    payload = {
        "merchantId": s.phonepe_active_merchant_id,
        "merchantTransactionId": merchant_order_id,
        # Not a real customer identifier — PhonePe requires SOME
        # merchantUserId, but this portal has no PhonePe-specific customer
        # account concept, so a value derived from the order id (not the
        # customer's mobile/PII) is used.
        "merchantUserId": f"MU{merchant_order_id[:30]}",
        "amount": round(amount_rupees * 100),
        "redirectUrl": redirect_url,
        "redirectMode": "REDIRECT",
        "callbackUrl": f"{s.portal_base_url}/payment/phonepe/webhook",
        "paymentInstrument": {"type": "PAY_PAGE"},
    }
    b64_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    checksum = _checksum(b64_payload + "/pg/v1/pay")
    headers = {"Content-Type": "application/json", "X-VERIFY": checksum, "accept": "application/json"}
    url = f"{s.phonepe_active_host_url}/pg/v1/pay"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json={"request": b64_payload}, headers=headers)
        data = resp.json()
    except (httpx.TransportError, httpx.TimeoutException, ValueError) as exc:
        raise PhonePeError(f"create_order request failed: {exc}") from exc
    if not data.get("success"):
        raise PhonePeError(f"create_order rejected: {data.get('code')} {data.get('message')}")
    try:
        redirect = data["data"]["instrumentResponse"]["redirectInfo"]["url"]
    except (KeyError, TypeError) as exc:
        raise PhonePeError(f"create_order: unexpected response shape {data!r}") from exc
    return redirect, merchant_order_id


async def _fetch_status(merchant_order_id: str) -> dict:
    s = get_settings()
    path = f"/pg/v1/status/{s.phonepe_active_merchant_id}/{merchant_order_id}"
    checksum = _checksum(path)
    headers = {
        "Content-Type": "application/json", "X-VERIFY": checksum,
        "X-MERCHANT-ID": s.phonepe_active_merchant_id, "accept": "application/json",
    }
    url = f"{s.phonepe_active_host_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
        return resp.json()
    except (httpx.TransportError, httpx.TimeoutException, ValueError) as exc:
        raise PhonePeError(f"status check request failed: {exc}") from exc


_SUCCESS_CODES = {"PAYMENT_SUCCESS"}
_FAILURE_CODES = {"PAYMENT_ERROR", "PAYMENT_DECLINED", "PAYMENT_CANCELLED"}


async def check_status(merchant_order_id: str) -> str:
    """Returns a normalized state: PENDING | COMPLETED | FAILED (mapped
    from PhonePe's own `code` field — pending/unrecognized codes are
    treated as PENDING rather than assumed failed)."""
    data = await _fetch_status(merchant_order_id)
    code = data.get("code", "")
    if code in _SUCCESS_CODES:
        return "COMPLETED"
    if code in _FAILURE_CODES:
        return "FAILED"
    return "PENDING"


async def transaction_id_for(merchant_order_id: str) -> str:
    """Best-effort PhonePe transaction id (their UTR-equivalent) for a
    completed order, for display on the receipt — blank if unavailable."""
    try:
        data = await _fetch_status(merchant_order_id)
    except PhonePeError:
        return ""
    return (data.get("data") or {}).get("transactionId", "") or ""


def validate_webhook(auth_header: str, raw_body: str) -> dict:
    """Verifies an incoming callback's X-VERIFY header against the same
    salt-key checksum used for outbound requests, then decodes the
    base64-wrapped payload. Raises PhonePeError if the checksum doesn't
    match or the body is malformed. Returns a plain dict — NOT the shape
    of PhonePe's v2 SDK's CallbackResponse, since this integration doesn't
    use that SDK — with keys: merchant_order_id, state (PENDING|COMPLETED|
    FAILED, same normalization as check_status), transaction_id."""
    try:
        body = json.loads(raw_body)
        b64_response = body["response"]
    except (ValueError, KeyError) as exc:
        raise PhonePeError(f"webhook: malformed body: {exc}") from exc

    expected = _checksum(b64_response)
    if auth_header != expected:
        raise PhonePeError("webhook: X-VERIFY checksum mismatch")

    try:
        decoded = json.loads(base64.b64decode(b64_response).decode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise PhonePeError(f"webhook: could not decode payload: {exc}") from exc

    data = decoded.get("data") or {}
    code = decoded.get("code", "")
    if code in _SUCCESS_CODES:
        state = "COMPLETED"
    elif code in _FAILURE_CODES:
        state = "FAILED"
    else:
        state = "PENDING"
    return {
        "merchant_order_id": data.get("merchantTransactionId", ""),
        "state": state,
        "transaction_id": data.get("transactionId", "") or "",
    }
