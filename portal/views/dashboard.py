"""Dashboard + loan detail. Everything rendered from live LMS calls —
the portal holds no loan data."""

import asyncio

from django.http import HttpResponseRedirect
from django.shortcuts import render

from portal.decorators import assert_loan_access, require_session
from portal.lms import get_lms
from portal.services import session_service
from portal.services.allcloud_auth import LMSError
from portal.services.audit import audit


async def index(request):
    sess = await session_service.load_session(request)
    return HttpResponseRedirect("/dashboard" if sess else "/login")


@require_session
async def dashboard(request, sess):
    lms = get_lms()
    try:
        loans = await lms.get_loans_by_mobile(sess.mobile)
    except LMSError:
        return render(request, "dashboard.html", {"sess": sess, "loans": None, "lms_down": True})
    # keep the IDOR allow-list fresh on every dashboard view
    await session_service.update_finance_ids(
        sess, [str(l.finance_id) for l in loans if l.finance_id]
    )
    # Per-loan LCC summary (GetLccDetailsByAgreementNo) — much more reliable
    # than GetLoanByMobileNumber's own EMI/overdue/status fields.
    # GetLoanAgreementNoAsync (agr) is fetched too: it's the only reliable
    # source for the customer's real name and the true next-due date —
    # LCC's InstallmentDueDate turned out to be the CURRENT (often
    # overdue/past) installment's date, not the genuinely upcoming one.
    # Profile (GetCustomerSearch) fetched alongside — powers the dashboard's
    # profile picture/name. Never persisted (PhotoURL is a short-lived
    # presigned S3 URL anyway), only ever rendered from this live call.
    lcc_list, agr_list, customers = await asyncio.gather(
        asyncio.gather(*(lms.get_lcc_details(l.agreement_no) for l in loans), return_exceptions=True),
        asyncio.gather(*(lms.get_loan_by_agreement(l.agreement_no) for l in loans), return_exceptions=True),
        lms.get_customer_search(sess.mobile),
        return_exceptions=True,
    )
    customer = customers[0] if (not isinstance(customers, Exception) and customers) else None
    rows = []
    customer_name = ""
    for loan, lcc, agr in zip(loans, lcc_list, agr_list):
        lcc = lcc if not isinstance(lcc, Exception) else None
        agr_match = None
        if not isinstance(agr, Exception):
            agr_match = next(
                (l for l in agr if l.agreement_no.upper() == loan.agreement_no.upper()), None
            )
        rows.append({"loan": loan, "lcc": lcc, "agr": agr_match})
        if not customer_name and agr_match and agr_match.primary_customer_name:
            customer_name = agr_match.primary_customer_name

    await audit(request, "dashboard_view", session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "dashboard.html",
                  {"sess": sess, "rows": rows, "lms_down": False, "customer_name": customer_name,
                   "customer": customer})


@require_session
async def profile_page(request, sess):
    lms = get_lms()
    customer = None
    try:
        customers = await lms.get_customer_search(sess.mobile)
        customer = customers[0] if customers else None
    except LMSError:
        customer = None
    await audit(request, "profile_view", session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "profile.html", {"sess": sess, "customer": customer})


@require_session
async def loan_detail(request, sess, finance_id: str):
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    loans = await lms.get_loans_by_mobile(sess.mobile)
    loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    dues = await lms.get_repayment_for_loan(finance_id)  # live, never cached
    await audit(request, "loan_view", detail=f"finance_id={finance_id}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "loan_detail.html", {"sess": sess, "loan": loan, "dues": dues})
