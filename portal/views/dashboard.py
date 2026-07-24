"""Dashboard + loan detail. Everything rendered from live LMS calls —
the portal holds no loan data."""

import asyncio
from datetime import timedelta

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone

from portal.config import get_settings
from portal.decorators import assert_loan_access, require_session
from portal.lms import get_lms
from portal.services import blocked_loans_service, device_trust_service, multi_lms, session_service


async def index(request):
    sess = await session_service.load_session(request)
    return HttpResponseRedirect("/dashboard" if sess else "/login")


@require_session
async def dashboard(request, sess):
    # Full 3-tenant scan (SMSquare + Padmasai + Sreemani) only periodically
    # (full_lender_rescan_minutes) — every other dashboard view re-checks
    # ONLY the tenant(s) already known from finance_lenders, since for a
    # customer who holds a loan at just one lender (the common case), the
    # other two are guaranteed-empty calls on every single page view. A
    # full scan is still what catches a brand-new loan at a different
    # lender; it just doesn't need to happen on every request to do that.
    rescan_due = (
        sess.last_lender_scan_at is None
        or timezone.now() - sess.last_lender_scan_at
        > timedelta(minutes=get_settings().full_lender_rescan_minutes)
    )
    did_full_scan = rescan_due
    if rescan_due:
        tagged_loans = await multi_lms.loans_by_mobile_all_tenants(sess.mobile)
    else:
        known_lenders = list(dict.fromkeys(sess.finance_lenders.values()))
        tagged_loans = await multi_lms.loans_for_known_lenders(sess.mobile, known_lenders)
        if not tagged_loans:
            # Cache came up empty (e.g. the known loan closed) — fall back
            # to a full scan for this one request rather than showing "no
            # loans" to someone who may have moved to a different lender.
            tagged_loans = await multi_lms.loans_by_mobile_all_tenants(sess.mobile)
            did_full_scan = True

    if not tagged_loans:
        return render(request, "dashboard.html", {"sess": sess, "loans": None, "lms_down": True})

    # Filter out any loan ops has specifically cut off portal access to
    # (see models.BlockedLoan / decorators.assert_loan_access) — it simply
    # doesn't appear here, rather than showing with an error. If that
    # leaves nothing, this reuses the exact same "no active loans, contact
    # us" rendering as a customer with genuinely zero loans (see
    # dashboard.html's `{% if lms_down or not rows %}`) — done BEFORE the
    # LCC/agreement gather below so a hidden loan's data isn't even fetched.
    pairs = [(str(loan.finance_id), lender) for lender, loan in tagged_loans if loan.finance_id]
    blocked_ids = await blocked_loans_service.blocked_finance_ids(pairs)
    tagged_loans = [(lender, loan) for lender, loan in tagged_loans if str(loan.finance_id) not in blocked_ids]
    if not tagged_loans:
        return render(request, "dashboard.html", {"sess": sess, "loans": None, "lms_down": True})
    loans = [loan for _, loan in tagged_loans]

    # The three lookups below (LCC, agreement, customer profile) are
    # mutually independent — each only needs tagged_loans, already in hand
    # — so they're fired as ONE combined gather rather than three
    # sequential await points; only a full scan's session update
    # (session_service.update_finance_ids, a DB write) also gets folded in
    # here rather than awaited beforehand, since nothing before the
    # template render actually needs it to have landed first.
    distinct_lenders = list(dict.fromkeys(lender for lender, _ in tagged_loans))
    tasks = [
        asyncio.gather(
            *(get_lms(lender).get_lcc_details(loan.agreement_no) for lender, loan in tagged_loans),
            return_exceptions=True,
        ),
        asyncio.gather(
            *(get_lms(lender).get_loan_by_agreement(loan.agreement_no) for lender, loan in tagged_loans),
            return_exceptions=True,
        ),
        # Profile (GetCustomerSearch) — powers the dashboard's profile
        # picture/name. Never persisted (PhotoURL is a short-lived
        # presigned S3 URL anyway), only ever rendered from this live
        # call. Searched once per DISTINCT lender the customer actually
        # has loans at (usually just one); if they hold loans at more
        # than one, the first one found wins — this is a low-stakes
        # display-only field, not worth a product decision on.
        asyncio.gather(
            *(get_lms(lender).get_customer_search(sess.mobile) for lender in distinct_lenders),
            return_exceptions=True,
        ),
    ]
    # Only a full scan updates finance_ids/finance_lenders (and bumps
    # last_lender_scan_at) — the cached path deliberately leaves the
    # session untouched, see update_finance_ids' docstring for why.
    if did_full_scan:
        finance_ids = [str(l.finance_id) for l in loans if l.finance_id]
        finance_lenders = {str(l.finance_id): lender for lender, l in tagged_loans if l.finance_id}
        tasks.append(session_service.update_finance_ids(sess, finance_ids, finance_lenders))

    lcc_list, agr_list, customer_results, *_ = await asyncio.gather(*tasks)
    customer = None
    for result in customer_results:
        if not isinstance(result, Exception) and result:
            customer = result[0]
            break

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

    # Proactive "set up a PIN?" nudge — opt-in, so only shown to a browser
    # that doesn't already have one (device_trust_service.load_device) and
    # hasn't been dismissed here before (see dismiss_pin_prompt). Only
    # surfaced on the real dashboard (not the no-loans/lms_down branch
    # above), since prompting before there's anything to actually use the
    # portal for doesn't make much sense.
    device = await device_trust_service.load_device(request)
    show_pin_prompt = device is None and not request.COOKIES.get("smsq_pin_dismissed")

    return render(request, "dashboard.html",
                  {"sess": sess, "rows": rows, "lms_down": False, "customer_name": customer_name,
                   "customer": customer, "show_pin_prompt": show_pin_prompt})


async def dismiss_pin_prompt(request):
    """Not @require_session — the banner's own form always has a live
    session at the moment it's shown, but there's nothing session-specific
    in dismissing it, and keeping this endpoint simple (just a cookie
    write) avoids a redirect-to-login edge case if the session happens to
    expire in the same instant as the click."""
    response = HttpResponse(status=204)
    response.set_cookie("smsq_pin_dismissed", "1", max_age=30 * 24 * 3600, samesite="Lax")
    return response


@require_session
async def profile_page(request, sess):
    results = await multi_lms.search_customer_all_tenants(sess.mobile)
    customer = results[0][1] if results else None
    device = await device_trust_service.load_device(request)
    pin_enabled = device is not None and device.mobile == sess.mobile
    return render(request, "profile.html",
                  {"sess": sess, "customer": customer, "pin_enabled": pin_enabled})


@require_session
async def loan_detail(request, sess, finance_id: str):
    await assert_loan_access(sess, finance_id, request)
    lender = sess.finance_lenders.get(str(finance_id), "smsquare")
    lms = get_lms(lender)
    loans = await lms.get_loans_by_mobile(sess.mobile)
    loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    dues = await lms.get_repayment_for_loan(finance_id)  # live, never cached
    return render(request, "loan_detail.html", {"sess": sess, "loan": loan, "dues": dues})
