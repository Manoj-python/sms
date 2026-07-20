"""Typed AllCloud LMS client. All portal loan data flows through here.

Honours LMS_MOCK=true (fixtures, no network). Response payloads are parsed
tolerantly — AllCloud sometimes wraps lists in {"data": [...]} style
envelopes, so `_unwrap_list` normalizes before Pydantic validation.
"""

import json
import logging
from urllib.parse import quote

from portal.config import Settings, get_settings
from portal.lms_schemas import (
    CustomerSearchResult,
    LccDetails,
    LoanSummary,
    QRCodeResponse,
    RepaymentDue,
)
from portal.services import mock_lms
from portal.services.allcloud_auth import AllCloudAuth, minify

logger = logging.getLogger("allcloud.client")


def _maybe_json_decode(payload):
    """Some AllCloud endpoints (confirmed live: GetLccDetailsByAgreementNo)
    double-encode — the HTTP body is a JSON string containing JSON, so
    resp.json() yields a Python str instead of a dict/list. Decode once
    more in that case."""
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except ValueError:
            return payload
    return payload


def _unwrap_list(payload) -> list:
    payload = _maybe_json_decode(payload)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "Data", "result", "Result", "Items", "items", "value"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                return [inner]
        return [payload] if payload else []
    return []


def _unwrap_obj(payload) -> dict:
    payload = _maybe_json_decode(payload)
    if isinstance(payload, dict):
        for key in ("data", "Data", "result", "Result", "value"):
            if isinstance(payload.get(key), dict):
                return payload[key]
        return payload
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    return {}


class AllCloudClient:
    def __init__(self, settings: Settings | None = None, log_sink=None):
        self.settings = settings or get_settings()
        self.auth = AllCloudAuth(self.settings)
        self.log_sink = log_sink  # callable(dict) -> persists to lms_api_log

    async def aclose(self) -> None:
        await self.auth.aclose()

    # Each call is routed to the host + auth model appropriate to its kind
    # (lookup / payment) — see config.py's *_base_url and *_auth_header
    # properties for the prod-vs-UAT resolution. There is deliberately no
    # saverepayment call — see payment_service.py.

    async def _get_lookup(self, path: str):
        url = f"{self.settings.lookup_base_url}{path}"
        return await self.auth.call_lms(
            "GET", url, log_sink=self.log_sink,
            static_auth_header=self.settings.lookup_auth_header,
        )

    async def _post_payment(self, path: str, body: dict):
        url = f"{self.settings.payment_base_url}{path}"
        return await self.auth.call_lms(
            "POST", url, body=body, log_sink=self.log_sink,
            static_auth_header=self.settings.payment_auth_header,
        )

    async def _post_lcc(self, path: str, body: dict):
        url = f"{self.settings.payment_base_url}{path}"
        return await self.auth.call_lms(
            "POST", url, body=body, log_sink=self.log_sink,
            static_auth_header=self.settings.lcc_auth_header,
        )

    # --- customer / loans ----------------------------------------------------

    async def get_customer_search(self, mobile: str) -> list[CustomerSearchResult]:
        """Verify a mobile exists in the LMS before sending any OTP."""
        raw = (
            mock_lms.customer_search(mobile)
            if self.settings.lms_mock
            else await self._get_lookup(f"/api/Customer/GetCustomerSearch?Contact={quote(mobile)}")
        )
        return [CustomerSearchResult.model_validate(r) for r in _unwrap_list(raw)]

    async def get_loans_by_mobile(self, mobile: str) -> list[LoanSummary]:
        raw = (
            mock_lms.loans_by_mobile(mobile)
            if self.settings.lms_mock
            else await self._get_lookup(
                f"/api/loan/GetLoanByMobileNumber?ContactNumber={quote(mobile)}"
            )
        )
        return [LoanSummary.model_validate(r) for r in _unwrap_list(raw)]

    async def get_loan_by_agreement(self, agreement_no: str) -> list[LoanSummary]:
        """Alternate login lookup + loan detail (e.g. LNTSPAR-240300005)."""
        raw = (
            mock_lms.loan_by_agreement(agreement_no)
            if self.settings.lms_mock
            else await self._get_lookup(
                f"/api/loan/GetLoanAgreementNoAsync?strAgreementNo={quote(agreement_no)}"
            )
        )
        return [LoanSummary.model_validate(r) for r in _unwrap_list(raw)]

    # --- dues / payments -------------------------------------------------------

    async def get_repayment_for_loan(self, finance_id: str) -> RepaymentDue:
        """Live dues. NEVER cache this — always called fresh per page view."""
        raw = (
            mock_lms.repayment_for_loan(finance_id)
            if self.settings.lms_mock
            else await self._get_lookup(
                f"/api/Repayment/GetRepaymentForLoanByLoanId?FinanceId={quote(str(finance_id))}"
            )
        )
        return RepaymentDue.model_validate(_unwrap_obj(raw))

    async def get_lcc_details(self, agreement_no: str, finance_id: str = "0") -> LccDetails:
        """Loan collection summary — confirmed live 2026-07-14. Richer than
        GetLoanByMobileNumber for dashboard display (clean Status,
        InstallmentDueDate, TotalDues, LPCDue)."""
        body = {"AgreementNo": agreement_no, "FinanceId": str(finance_id)}
        raw = (
            mock_lms.lcc_details(agreement_no)
            if self.settings.lms_mock
            else await self._post_lcc("/api/voicecall/GetLccDetailsByAgreementNo", body)
        )
        return LccDetails.model_validate(_unwrap_obj(raw))

    async def get_qr_code(
        self,
        finance_id: str,
        due_amount: float,
        collection_charges: float,
        lpi_amount: float,
        *,
        show_qr: bool = True,
        sms_link: bool = False,
        collection_type: int | None = None,
        is_advance_receipt: bool = False,
    ) -> QRCodeResponse:
        total = round(due_amount + collection_charges + lpi_amount, 2)
        body = {
            "FinanceId": finance_id,
            "DueAmount": due_amount,
            "CollectionCharges": collection_charges,
            "LPIAmount": lpi_amount,
            "ShowQR": show_qr,
            "SMSLink": sms_link,
            "HandLoan": 0,
            "VasDue": 0,
            # Confirmed live shape (chatloan4.py): AllCloud expects this
            # flag as a STRING, not a JSON boolean.
            "IsAdvanceReceipt": "true" if is_advance_receipt else "false",
            "CollectionType": collection_type
            if collection_type is not None
            else self.settings.lms_collection_type_default,
            "TotalAmount": total,  # must equal sum of components
        }
        raw = (
            mock_lms.qr_code(body)
            if self.settings.lms_mock
            else await self._post_payment("/api/paymentgateway/GetQRCode", body)
        )
        return QRCodeResponse.model_validate(_unwrap_obj(raw))

    # --- diagnostics ------------------------------------------------------------

    async def raw_probe(self, method: str, path: str, body: dict | None = None):
        """Helper behind /dev/lms-probe: returns the raw payload so
        undocumented schemas can be inspected. GET -> lookup host/token;
        POST -> payment gateway host/token."""
        if self.settings.lms_mock:
            return {"mock": True, "note": "LMS_MOCK=true — raw probe not meaningful"}
        if method.upper() == "GET":
            return await self._get_lookup(path)
        return await self._post_payment(path, body or {})


# module-level singleton (created lazily by dependencies.get_lms)
_client: AllCloudClient | None = None


def get_client(log_sink=None) -> AllCloudClient:
    global _client
    if _client is None:
        _client = AllCloudClient(log_sink=log_sink)
    elif log_sink is not None:
        _client.log_sink = log_sink
    return _client


__all__ = ["AllCloudClient", "get_client", "minify"]
