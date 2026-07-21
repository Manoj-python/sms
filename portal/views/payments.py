"""Dues display, payment options, UPI QR, confirmation, receipt.

Compliance notes baked into the flow:
- Full charge break-up (EMI / penal LPI / collection charges) disclosed
  BEFORE any payment action (RBI penal charges circular).
- A gateway success is never shown as a failure. No saverepayment call is
  made (host unconfirmed — see payment_service.py); ops reconciles into
  AllCloud out-of-band.
"""

from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render

from portal.decorators import assert_loan_access, require_session
from portal.lms import get_lms
from portal.services import payment_service
from portal.services.allcloud_auth import LMSError
from portal.services.audit import audit
from portal.services.foreclosure_statement_pdf import build_foreclosure_statement_pdf, compute_foreclosure
from portal.services.installment_receipt_pdf import (
    _amount_for_date,
    _dmy,
    build_charge_receipt_pdf,
    build_installment_receipt_pdf,
    charge_receipt_items,
    receipt_dates,
    voucher_breakdown,
)
from portal.services.receipt_pdf import build_receipt_pdf
from portal.services.statement_pdf import _last_date, _paid_amount, build_statement_pdf


# Statement/payment-history downloads are gated behind dues: a customer 3+
# EMIs overdue is routed to WhatsApp instead, per an explicit product
# decision (not a technical limitation) — collections wants a human
# conversation with those customers rather than a self-serve document.
MAX_EMI_DUE_FOR_DOWNLOADS = 3

# The foreclosure statement gets a looser threshold — self-serve payoff
# figures stay available up to 4 EMIs overdue since that's exactly the
# customer trying to close out; only beyond that (5+) is a human
# conversation required (per explicit product decision).
MAX_EMI_DUE_FOR_FORECLOSURE = 4


async def _contact_required(request, sess, finance_id: str, loan, action: str, audit_action: str, reason: str):
    """Renders the "contact us" page and audits why access was blocked —
    shared by the dues gate and the seized-vehicle gate below."""
    await audit(
        request, audit_action,
        detail=f"finance_id={finance_id} agreement_no={loan.agreement_no} "
               f"emi_due_count={loan.emi_due_count} action={action}",
        session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile,
    )
    return render(request, "contact_required.html", {
        "sess": sess, "finance_id": finance_id, "emi_due_count": loan.emi_due_count, "reason": reason,
    })


async def _dues_gate(request, sess, finance_id: str, loan, action: str):
    """None if downloads are allowed; otherwise a rendered "contact us" response."""
    if loan.emi_due_count < MAX_EMI_DUE_FOR_DOWNLOADS:
        return None
    return await _contact_required(
        request, sess, finance_id, loan, action, "download_blocked_dues_contact_requested", "dues",
    )


async def _foreclosure_dues_gate(request, sess, finance_id: str, loan, action: str):
    """Same idea as _dues_gate but with the looser MAX_EMI_DUE_FOR_FORECLOSURE
    threshold — see that constant's comment."""
    if loan.emi_due_count <= MAX_EMI_DUE_FOR_FORECLOSURE:
        return None
    return await _contact_required(
        request, sess, finance_id, loan, action, "foreclosure_blocked_dues_contact_requested", "dues",
    )


async def _seize_gate(request, sess, finance_id: str, loan, lcc, action: str):
    """None if access is allowed; otherwise a rendered "contact us" response
    for a vehicle that's been repossessed — statement/payment-history/
    receipt documents on a seized vehicle need a human conversation with
    collections, not a self-serve download."""
    if not (lcc and lcc.is_seized):
        return None
    return await _contact_required(
        request, sess, finance_id, loan, action, "download_blocked_seized_contact_requested", "seized",
    )


async def _load_agreement_loan_and_customer(lms, sess, finance_id: str):
    """Shared by statement_pdf/installment_receipt_pdf/charge_receipt_pdf —
    GetLoanAgreementNoAsync is the only source rich enough for a receipt
    (RepaymentSchedules with LPC/CollectionCharges, VASs) unlike
    GetLoanByMobileNumber's own thinner fields."""
    loans = await lms.get_loans_by_mobile(sess.mobile)
    base_loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    if base_loan is None:
        return None, None, None
    agr_loans = await lms.get_loan_by_agreement(base_loan.agreement_no)
    loan = next(
        (l for l in agr_loans if l.agreement_no.upper() == base_loan.agreement_no.upper()),
        base_loan,
    )
    customers = await lms.get_customer_search(sess.mobile)
    customer = customers[0] if customers else None
    lcc = None
    try:
        lcc = await lms.get_lcc_details(loan.agreement_no)
    except LMSError:
        lcc = None
    return loan, customer, lcc


@require_session
async def pay_page(request, sess, finance_id: str):
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    dues = await lms.get_repayment_for_loan(finance_id)  # live dues
    loans = await lms.get_loans_by_mobile(sess.mobile)
    loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    # GetLoanByMobileNumber's own fields are unreliable — GetLoanAgreementNoAsync
    # is the accurate, much richer source (customer name, tenure, EMI counts,
    # VAS/late charges) whenever the lookup works.
    if loan:
        try:
            agr_loans = await lms.get_loan_by_agreement(loan.agreement_no)
            match = next(
                (l for l in agr_loans if l.agreement_no.upper() == loan.agreement_no.upper()),
                None,
            )
            if match:
                loan = match
        except LMSError:
            pass
    # LCC's InstallmentDueDate blank -> loan past its full EMI tenure with
    # no more scheduled installments (see dashboard.html) — same "Expired"
    # signal shown here, since this page's Loan Details card also displays
    # Next due.
    lcc = None
    if loan:
        try:
            lcc = await lms.get_lcc_details(loan.agreement_no)
        except LMSError:
            lcc = None
    total_due_display = payment_service.capped_total_due(
        loan.overdue_amount if loan else 0.0,
        loan.lpi_dues if loan else 0.0,
        loan.total_vas_dues if loan else 0.0,
    )
    min_emi_amount = payment_service.minimum_emi_amount(
        loan.regular_emi_amount if loan else 0.0,
        total_due_display,
        loan.emi_due_count if loan else 0.0,
    )
    max_part_amount = payment_service.max_part_payment(loan.loan_amount if loan else 0.0)
    late_charges_display = payment_service.late_charges_display(loan.lpi_dues if loan else 0.0)
    await audit(request, "pay_page_view", detail=f"finance_id={finance_id}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "pay.html", {"sess": sess, "loan": loan, "dues": dues, "lcc": lcc,
                                        "finance_id": finance_id, "min_emi_amount": min_emi_amount,
                                        "max_part_amount": max_part_amount,
                                        "late_charges_display": late_charges_display,
                                        "total_due_display": total_due_display})


@require_session
async def generate_qr(request, sess, finance_id: str):
    """HTMX: creates the pg_transaction and renders the customer's chosen
    payment method — Pay Now gateway button."""
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    option = request.POST.get("option", "")
    part_amount = request.POST.get("part_amount")
    part_amount = float(part_amount) if part_amount else None
    method = request.POST.get("method", "paynow")  # paynow -> ShowQR:false | qr -> ShowQR:true
    want_sms_link = bool(request.POST.get("want_sms_link"))

    # Re-fetch fresh, never trust the form. GetLoanAgreementNoAsync (loan) is
    # the accurate source for these totals — see pay_page/pay.html.
    loans = await lms.get_loans_by_mobile(sess.mobile)
    base_loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    loan = base_loan
    if base_loan:
        try:
            agr_loans = await lms.get_loan_by_agreement(base_loan.agreement_no)
            match = next(
                (l for l in agr_loans if l.agreement_no.upper() == base_loan.agreement_no.upper()),
                None,
            )
            if match:
                loan = match
        except LMSError:
            pass
    total = payment_service.capped_total_due(
        loan.overdue_amount if loan else 0.0,
        loan.lpi_dues if loan else 0.0,
        loan.total_vas_dues if loan else 0.0,
    )
    emi = loan.regular_emi_amount if loan else 0.0
    loan_amount = loan.loan_amount if loan else 0.0
    emi_due_count = loan.emi_due_count if loan else 0.0

    try:
        option, pay_amount = payment_service.validate_amount(
            option, part_amount, total, emi, loan_amount, emi_due_count,
        )
    except ValueError as exc:
        error_key = str(exc)
        min_emi_amount = payment_service.minimum_emi_amount(emi, total, emi_due_count)
        # Re-renders the WHOLE form (not just a bare error) so the customer
        # can immediately fix the amount and resubmit — replacing #pay-box
        # with just an error message (the old behaviour) meant losing the
        # radio options / amount field / Pay Now button entirely, with no
        # way back short of a full page reload.
        ctx = {
            "error_key": error_key, "finance_id": finance_id,
            "min_emi_amount": min_emi_amount,
            "max_part_amount": payment_service.max_part_payment(loan_amount),
            "total_due_display": total, "selected_option": option,
            "part_amount_value": part_amount,
        }
        if error_key == "pay_min_part":
            ctx["min_amount"] = min_emi_amount
        elif error_key == "pay_exceeds_max":
            ctx["max_amount"] = payment_service.max_part_payment(loan_amount)
        return render(request, "partials/pay_form.html", ctx)

    # Charges are collected in full first; the remainder is the EMI/principal
    # leg. lpi uses the same capped late-charges figure as `total` above —
    # otherwise a real lpi_dues above the cap would consume the whole
    # payment as "LPI", leaving nothing for principal/collection.
    lpi = min(payment_service.late_charges_display(loan.lpi_dues) if loan else 0.0, pay_amount)
    coll = min(float(loan.total_vas_dues) if loan else 0.0, max(pay_amount - lpi, 0.0))
    principal = round(pay_amount - lpi - coll, 2)

    txn = await payment_service.create_transaction(
        session_id=sess.id,
        mobile=sess.mobile,
        finance_id=finance_id,
        agreement_no="",
        amount=principal,
        lpi_amount=lpi,
        collection_charges=coll,
        payment_option=option,
    )
    show_qr = method == "qr"
    try:
        qr = await lms.get_qr_code(
            finance_id=finance_id,
            due_amount=principal,
            collection_charges=coll,
            lpi_amount=lpi,
            show_qr=show_qr,
            sms_link=want_sms_link,
        )
    except LMSError:
        txn.status = "FAILED"
        txn.last_error = "GetQRCode failed"
        await txn.asave()
        return render(request, "partials/pay_form.html", {
            "error_key": "err_lms_down", "finance_id": finance_id,
            "min_emi_amount": payment_service.minimum_emi_amount(emi, total, emi_due_count),
            "max_part_amount": payment_service.max_part_payment(loan_amount),
            "total_due_display": total, "selected_option": option,
            "part_amount_value": part_amount,
        })

    txn.lms_receipt_ref = qr.reference[:80]
    await txn.asave()
    # No separate "I have completed the payment" step — the gateway page is
    # the actual payment action, and the portal can't verify completion from
    # here (no server-to-server callback), so the transaction is marked
    # GATEWAY_SUCCESS as soon as the checkout link is generated. Never shown
    # as a failure; ops reconciles into AllCloud out-of-band.
    txn = await payment_service.confirm_gateway_payment(txn, utr="")
    await audit(request, "qr_generated",
                detail=f"txn={txn.id} finance_id={finance_id} amount={txn.total_amount} method={method}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "partials/payment_result.html", {"txn": txn, "qr": qr})


@require_session
async def downloads_page(request, sess, finance_id: str):
    """Statement + receipts in one place, listed date-wise rather than
    installment-wise — a single voucher can span several installments, so
    the payment date is the natural unit for a customer looking for "the
    receipt for what I paid on X"."""
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "downloads_page")
    if gated is not None:
        return gated
    gated = await _dues_gate(request, sess, finance_id, loan, "downloads_page")
    if gated is not None:
        return gated

    await audit(request, "downloads_page_view", detail=f"finance_id={finance_id} agreement_no={loan.agreement_no}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "downloads.html", {
        "sess": sess, "loan": loan, "finance_id": finance_id,
        "dates": receipt_dates(loan),
    })


@require_session
async def statement_pdf(request, sess, finance_id: str):
    """Loan statement-of-account — built from live GetCustomerSearch +
    GetLoanAgreementNoAsync data (see statement_pdf.py module docstring for
    what's included vs. omitted relative to AllCloud's own internal export)."""
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    loans = await lms.get_loans_by_mobile(sess.mobile)
    base_loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    if base_loan is None:
        return HttpResponseNotFound()
    try:
        agr_loans = await lms.get_loan_by_agreement(base_loan.agreement_no)
        loan = next(
            (l for l in agr_loans if l.agreement_no.upper() == base_loan.agreement_no.upper()),
            base_loan,
        )
        customers = await lms.get_customer_search(sess.mobile)
        customer = customers[0] if customers else None
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    try:
        lcc = await lms.get_lcc_details(loan.agreement_no)
    except LMSError:
        lcc = None

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "statement_pdf")
    if gated is not None:
        return gated
    gated = await _dues_gate(request, sess, finance_id, loan, "statement_pdf")
    if gated is not None:
        return gated

    pdf = build_statement_pdf(customer, loan, lcc)
    await audit(request, "statement_downloaded", detail=f"finance_id={finance_id} agreement_no={loan.agreement_no}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return HttpResponse(
        content=pdf,
        content_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="statement_{loan.agreement_no}.pdf"'},
    )


@require_session
async def foreclosure_statement_pdf(request, sess, finance_id: str):
    """Foreclosure/payoff statement — see foreclosure_statement_pdf.py's
    module docstring for the two computed line items (Fore-Closure Charges,
    Broken Period Interest) and their confirmed business rules. Uses the
    looser MAX_EMI_DUE_FOR_FORECLOSURE threshold, not the standard dues
    gate: self-serve stays available up through 4 EMIs overdue since that's
    exactly the customer trying to close the loan out; only beyond that (5+)
    does it route to a human conversation. Also gated on seizure, same as
    statement/payment-history/receipts."""
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "foreclosure_statement_pdf")
    if gated is not None:
        return gated
    gated = await _foreclosure_dues_gate(request, sess, finance_id, loan, "foreclosure_statement_pdf")
    if gated is not None:
        return gated

    pdf = build_foreclosure_statement_pdf(customer, loan, lcc)
    await audit(request, "foreclosure_statement_downloaded",
                detail=f"finance_id={finance_id} agreement_no={loan.agreement_no}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return HttpResponse(
        content=pdf,
        content_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="foreclosure_{loan.agreement_no}.pdf"'},
    )


@require_session
async def receipt_pdf(request, sess, txn_id: int):
    txn = await payment_service.get_owned_txn(txn_id, sess.id)
    if txn is None or txn.status != "RECONCILED":
        return HttpResponseNotFound()
    pdf = build_receipt_pdf(txn, customer_name=sess.customer_name)
    await audit(request, "receipt_downloaded", detail=f"txn={txn.id}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return HttpResponse(
        content=pdf,
        content_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{txn.receipt_no}.pdf"'},
    )


@require_session
async def receipt_by_date_pdf(request, sess, finance_id: str, target_date: str):
    """Payment voucher for a given date — date-driven, not installment-
    driven: a single voucher can span more than one installment (see
    build_installment_receipt_pdf's docstring), so the date is the natural
    key, matching how the Downloads page lists receipts."""
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "receipt_by_date_pdf")
    if gated is not None:
        return gated

    target_date = _dmy(target_date)
    installment = next(
        (e for e in loan.repayment_schedules if _amount_for_date(e, target_date) > 0), None
    )
    if installment is None:
        return HttpResponseNotFound()

    pdf = build_installment_receipt_pdf(customer, loan, lcc, installment, target_date=target_date)
    await audit(request, "installment_receipt_downloaded",
                detail=f"finance_id={finance_id} agreement_no={loan.agreement_no} date={target_date}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return HttpResponse(
        content=pdf,
        content_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="receipt_{loan.agreement_no}_{target_date}.pdf"'
            )
        },
    )


@require_session
async def charge_receipt_pdf(request, sess, finance_id: str, target_date: str):
    """Standalone charge voucher (e.g. a lump-sum bounce-charge
    settlement) — see build_charge_receipt_pdf's docstring for how this
    differs from an EMI voucher."""
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "charge_receipt_pdf")
    if gated is not None:
        return gated

    target_date = _dmy(target_date)
    pdf = build_charge_receipt_pdf(customer, loan, lcc, target_date)
    await audit(request, "charge_receipt_downloaded",
                detail=f"finance_id={finance_id} agreement_no={loan.agreement_no} date={target_date}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return HttpResponse(
        content=pdf,
        content_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="charges_{loan.agreement_no}_{target_date}.pdf"'
            )
        },
    )


# --- in-portal HTML views ----------------------------------------------
# A responsive, mobile-friendly alternative to opening the PDF — same live
# data and same access gates as the PDF views above, just rendered as a
# normal page instead of a fixed-layout document. The PDF stays available
# from each of these pages (its own "Download PDF" link) for anyone who
# wants the file itself — this doesn't replace the PDF, just adds a faster
# way to look at it on a phone (no PDF viewer, no pinch-zoom).


@require_session
async def statement_view(request, sess, finance_id: str):
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    loans = await lms.get_loans_by_mobile(sess.mobile)
    base_loan = next((l for l in loans if str(l.finance_id) == str(finance_id)), None)
    if base_loan is None:
        return HttpResponseNotFound()
    try:
        agr_loans = await lms.get_loan_by_agreement(base_loan.agreement_no)
        loan = next(
            (l for l in agr_loans if l.agreement_no.upper() == base_loan.agreement_no.upper()),
            base_loan,
        )
        customers = await lms.get_customer_search(sess.mobile)
        customer = customers[0] if customers else None
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    try:
        lcc = await lms.get_lcc_details(loan.agreement_no)
    except LMSError:
        lcc = None

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "statement_view")
    if gated is not None:
        return gated
    gated = await _dues_gate(request, sess, finance_id, loan, "statement_view")
    if gated is not None:
        return gated

    total_dues = round(loan.overdue_amount + loan.lpi_dues + loan.total_vas_dues, 2)
    # Mirrors statement_pdf.py's repayment-schedule table — precomputed here
    # (not in the template) since PaidAmount/PaymentDate can be
    # comma-separated multi-payment strings that need the same parsing
    # statement_pdf.py already solved (see _paid_amount/_last_date there).
    schedule_rows = [
        {"entry": e, "paid": _paid_amount(e.paid_amount), "last_paid": _last_date(e.payment_date)}
        for e in loan.repayment_schedules
    ]
    await audit(request, "statement_viewed", detail=f"finance_id={finance_id} agreement_no={loan.agreement_no}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "documents/statement_view.html", {
        "sess": sess, "loan": loan, "customer": customer, "lcc": lcc,
        "finance_id": finance_id, "total_dues": total_dues, "schedule_rows": schedule_rows,
    })


@require_session
async def foreclosure_view(request, sess, finance_id: str):
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "foreclosure_view")
    if gated is not None:
        return gated
    gated = await _foreclosure_dues_gate(request, sess, finance_id, loan, "foreclosure_view")
    if gated is not None:
        return gated

    calc = compute_foreclosure(loan, lcc)
    await audit(request, "foreclosure_statement_viewed",
                detail=f"finance_id={finance_id} agreement_no={loan.agreement_no}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "documents/foreclosure_view.html", {
        "sess": sess, "loan": loan, "customer": customer, "lcc": lcc,
        "finance_id": finance_id, "calc": calc, "as_of_str": calc["_as_of"].strftime("%d-%m-%Y"),
    })


@require_session
async def receipt_by_date_view(request, sess, finance_id: str, target_date: str):
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "receipt_by_date_view")
    if gated is not None:
        return gated

    target_date = _dmy(target_date)
    installment = next(
        (e for e in loan.repayment_schedules if _amount_for_date(e, target_date) > 0), None
    )
    if installment is None:
        return HttpResponseNotFound()

    breakdown = voucher_breakdown(loan, target_date)
    await audit(request, "installment_receipt_viewed",
                detail=f"finance_id={finance_id} agreement_no={loan.agreement_no} date={target_date}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "documents/receipt_view.html", {
        "sess": sess, "loan": loan, "customer": customer, "lcc": lcc,
        "finance_id": finance_id, "target_date": target_date, "breakdown": breakdown,
    })


@require_session
async def charge_receipt_view(request, sess, finance_id: str, target_date: str):
    lms = get_lms()
    await assert_loan_access(lms, sess, finance_id, request)
    try:
        loan, customer, lcc = await _load_agreement_loan_and_customer(lms, sess, finance_id)
    except LMSError:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)
    if loan is None or customer is None:
        return render(request, "error.html", {"error_key": "err_lms_down"}, status=503)

    gated = await _seize_gate(request, sess, finance_id, loan, lcc, "charge_receipt_view")
    if gated is not None:
        return gated

    target_date = _dmy(target_date)
    charges = charge_receipt_items(loan, target_date)
    await audit(request, "charge_receipt_viewed",
                detail=f"finance_id={finance_id} agreement_no={loan.agreement_no} date={target_date}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "documents/charge_receipt_view.html", {
        "sess": sess, "loan": loan, "customer": customer, "lcc": lcc,
        "finance_id": finance_id, "target_date": target_date, "charges": charges,
        "total": sum(ch.amount for ch in charges),
    })


@require_session
async def payment_receipt_view(request, sess, txn_id: int):
    txn = await payment_service.get_owned_txn(txn_id, sess.id)
    if txn is None or txn.status != "RECONCILED":
        return HttpResponseNotFound()
    await audit(request, "receipt_viewed", detail=f"txn={txn.id}",
                session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    return render(request, "documents/payment_receipt_view.html", {"sess": sess, "txn": txn})
