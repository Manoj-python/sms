"""Staff-managed per-loan access deny-list — see models.BlockedLoan's
docstring for the product intent. Enforced from decorators.assert_loan_access
(the single existing choke point for every loan-scoped view) and used by
dashboard.py to filter a blocked loan out of the loan list entirely, rather
than showing it with an error."""

from portal.lms import get_lms
from portal.models import BlockedLoan
from portal.services import multi_lms
from portal.services.allcloud_auth import LMSError
from portal.services.crypto import mask_mobile


async def is_blocked(finance_id: str, lender: str) -> bool:
    return await BlockedLoan.objects.filter(finance_id=str(finance_id), lender=lender).aexists()


async def blocked_finance_ids(pairs: list[tuple[str, str]]) -> set[str]:
    """pairs: [(finance_id, lender), ...] for a customer's current loans —
    returns the subset of finance_ids (not (id, lender) tuples; a
    customer's own finance_ids are already unique to them) that are
    blocked. One query regardless of how many loans, unlike calling
    is_blocked per loan."""
    if not pairs:
        return set()
    lenders = {lender for _, lender in pairs}
    ids = {finance_id for finance_id, _ in pairs}
    blocked = BlockedLoan.objects.filter(finance_id__in=ids, lender__in=lenders)
    blocked_pairs = {(row.finance_id, row.lender) async for row in blocked}
    return {finance_id for finance_id, lender in pairs if (finance_id, lender) in blocked_pairs}


async def lookup_for_add(agreement_no: str) -> dict | None:
    """Live AllCloud lookup powering the staff add-form's auto-fill —
    same helpers already used by auth.agreement_lookup/multi_lms. Returns
    None if the agreement number isn't found in any tenant."""
    lender, loans = await multi_lms.find_agreement_any_tenant(agreement_no)
    if lender is None or not loans:
        return None
    loan = next((l for l in loans if l.agreement_no.upper() == agreement_no.upper()), loans[0])
    mobile = ""
    branch = ""
    try:
        lcc = await get_lms(lender).get_lcc_details(loan.agreement_no)
        mobile = lcc.customer_contact
        branch = lcc.branch
    except LMSError:
        pass
    return {
        "finance_id": str(loan.finance_id),
        "lender": lender,
        "agreement_no": loan.agreement_no,
        "customer_name": loan.primary_customer_name,
        "mobile": mobile,
        "branch": branch,
    }


async def create(
    *, finance_id: str, lender: str, agreement_no: str, customer_name: str,
    mobile: str, branch: str, centre: str, rsp_name: str, reason: str, blocked_by: str,
) -> BlockedLoan:
    return await BlockedLoan.objects.acreate(
        finance_id=str(finance_id), lender=lender, agreement_no=agreement_no,
        customer_name=customer_name, mobile=mobile, mobile_mask=mask_mobile(mobile) if mobile else "",
        branch=branch, centre=centre, rsp_name=rsp_name, reason=reason, blocked_by=blocked_by,
    )


def search(request):
    """Mirrors staff.py's _filtered_queryset style — every non-empty field
    ANDs together (a search across all 6 fields at once narrows down to
    the record staff actually mean, rather than OR'ing into noise)."""
    qs = BlockedLoan.objects.all().order_by("-created_at")
    loan_no = request.GET.get("loan_no", "").strip()
    name = request.GET.get("name", "").strip()
    mobile = request.GET.get("mobile", "").strip()
    branch = request.GET.get("branch", "").strip()
    centre = request.GET.get("centre", "").strip()
    rsp = request.GET.get("rsp", "").strip()
    if loan_no:
        qs = qs.filter(agreement_no__icontains=loan_no)
    if name:
        qs = qs.filter(customer_name__icontains=name)
    if mobile:
        qs = qs.filter(mobile_mask__icontains=mobile)
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if centre:
        qs = qs.filter(centre__icontains=centre)
    if rsp:
        qs = qs.filter(rsp_name__icontains=rsp)
    filters = {"loan_no": loan_no, "name": name, "mobile": mobile, "branch": branch, "centre": centre, "rsp": rsp}
    return qs, filters


async def delete(record_id: str) -> bool:
    deleted, _ = await BlockedLoan.objects.filter(pk=record_id).adelete()
    return deleted > 0
