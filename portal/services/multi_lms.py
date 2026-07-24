"""Cross-tenant search: a customer's loan may belong to SMSquare's own
portfolio or one of the two acquired portfolios (Padmasai, Sreemani), all
served by the same AllCloud platform as separate tenants (see config.py's
tenant_base_url/tenant_auth_header). These helpers query every tenant and
tag each result with which lender it came from, so the login flow never
needs the customer to say which lender they're with — see auth.py,
decorators.py's assert_loan_access, and dashboard.py for the call sites.
"""

import asyncio
import logging

from portal.config import get_settings
from portal.lms import get_lms
from portal.lms_schemas import CustomerSearchResult, LoanSummary
from portal.services.allcloud_auth import LMSError

logger = logging.getLogger("portal.multi_lms")

LENDERS: tuple[str, ...] = ("smsquare", "padmasai", "sreemani")


def _discovery_timeout() -> float:
    return get_settings().lms_discovery_timeout_seconds


async def _safe_customer_search(lender: str, mobile: str) -> list[CustomerSearchResult]:
    try:
        # retry_on_5xx=False: querying every tenant for a mobile that only
        # belongs to one means the other two are EXPECTED to miss — a 500
        # there is AllCloud's deterministic "not in this tenant" response,
        # not a transient error worth 2 retries' worth of backoff sleep.
        # timeout_seconds bounds a single hanging tenant from stalling the
        # whole parallel search — see call_lms's docstring.
        return await get_lms(lender).get_customer_search(
            mobile, retry_on_5xx=False, timeout_seconds=_discovery_timeout(),
        )
    except LMSError:
        logger.warning("customer_search failed for lender=%s", lender)
        return []


async def search_customer_all_tenants(mobile: str) -> list[tuple[str, CustomerSearchResult]]:
    """[(lender, CustomerSearchResult), ...] across all tenants — a tenant
    that errors or returns nothing is simply absent from the result, not a
    failure of the whole search."""
    results = await asyncio.gather(*(_safe_customer_search(l, mobile) for l in LENDERS))
    out: list[tuple[str, CustomerSearchResult]] = []
    for lender, res in zip(LENDERS, results):
        out.extend((lender, c) for c in res)
    return out


async def _safe_loans(lender: str, mobile: str) -> list[LoanSummary]:
    try:
        return await get_lms(lender).get_loans_by_mobile(mobile)
    except LMSError:
        logger.warning("get_loans_by_mobile failed for lender=%s", lender)
        return []


async def loans_by_mobile_all_tenants(mobile: str) -> list[tuple[str, LoanSummary]]:
    """[(lender, LoanSummary), ...] across all tenants — additive merge, not
    first-match, since a customer may genuinely hold loans at more than one
    lender post-acquisition."""
    results = await asyncio.gather(*(_safe_loans(l, mobile) for l in LENDERS))
    out: list[tuple[str, LoanSummary]] = []
    for lender, res in zip(LENDERS, results):
        out.extend((lender, loan) for loan in res)
    return out


async def loans_for_known_lenders(mobile: str, lenders: list[str]) -> list[tuple[str, LoanSummary]]:
    """Same shape as loans_by_mobile_all_tenants, but only queries the given
    (already-known) lenders — dashboard.py's cheaper path between full
    rescans: a customer who only holds an SMSquare loan doesn't need
    Padmasai/Sreemani re-checked on every single page view (both are
    guaranteed empty), just periodically (see config.full_lender_rescan_minutes).
    Loan DATA is still always fetched live here, never cached — only the
    "which tenants are worth asking" decision is."""
    distinct = list(dict.fromkeys(lenders)) or ["smsquare"]
    results = await asyncio.gather(*(_safe_loans(l, mobile) for l in distinct))
    out: list[tuple[str, LoanSummary]] = []
    for lender, res in zip(distinct, results):
        out.extend((lender, loan) for loan in res)
    return out


async def find_customer_priority(mobile: str) -> tuple[str | None, CustomerSearchResult | None]:
    """Login-eligibility check (send_otp): SMSquare is checked FIRST — most
    customers are SMSquare's own, so this avoids two extra network calls for
    the common case — and only falls through to Padmasai then Sreemani if
    SMSquare has no match at all (per explicit product decision). This
    decides whether an OTP gets sent at all; it deliberately does NOT
    determine what the customer sees post-login — once logged in, the
    dashboard/session still aggregate loans across every tenant that
    actually has one for this mobile (see loans_by_mobile_all_tenants),
    so a Padmasai/Sreemani loan is never hidden just because SMSquare
    happened to match first."""
    for lender in LENDERS:
        try:
            # retry_on_5xx=False / timeout_seconds — see
            # _safe_customer_search's comment; a tenant this mobile isn't
            # registered at is an EXPECTED miss for the two tenants that
            # turn out not to be the answer.
            results = await get_lms(lender).get_customer_search(
                mobile, retry_on_5xx=False, timeout_seconds=_discovery_timeout(),
            )
        except LMSError:
            continue
        if results:
            return lender, results[0]
    return None, None


async def _safe_agreement(lender: str, agreement_no: str) -> list[LoanSummary]:
    try:
        # retry_on_5xx=False / timeout_seconds — see find_agreement_any_tenant's docstring.
        return await get_lms(lender).get_loan_by_agreement(
            agreement_no, retry_on_5xx=False, timeout_seconds=_discovery_timeout(),
        )
    except LMSError:
        return []


async def find_agreement_any_tenant(agreement_no: str) -> tuple[str | None, list[LoanSummary]]:
    """agreement_lookup's no-OTP flow — an agreement number belongs to
    exactly one tenant, so there's at most one real match here, but the
    search itself is PARALLEL, not sequential: AllCloud returns a plain
    HTTP 500 (not 404) for "this agreement isn't in this tenant", which
    the shared retry/backoff logic in allcloud_auth.py treats as a
    transient failure worth retrying (2 retries, 0.5s/1s backoff) — correct
    for a genuine transient error, but pure wasted time for a deterministic
    miss. Sequential search paid that ~1.5s+ retry cost for EVERY dead-end
    tenant before reaching the right one (confirmed live: a Sreemani-only
    loan checked after SMSquare+Padmasai both missed took 7+ seconds).
    Parallel search bounds the total wait to whichever single tenant is
    slowest, not the sum of every miss."""
    results = await asyncio.gather(*(_safe_agreement(l, agreement_no) for l in LENDERS))
    for lender, loans in zip(LENDERS, results):
        if any(l.agreement_no.upper() == agreement_no.upper() for l in loans):
            return lender, loans
    return None, []
