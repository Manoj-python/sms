"""Login flows.

Primary: mobile -> GetCustomerSearch verification -> OTP -> session.
Alternate: agreement no. + mobile + DOB -> cross-verified -> session directly
(no OTP — a deliberate product choice; this is weaker than the OTP flow
since DOB isn't a strong secret). GetLoanAgreementNoAsync has NEITHER a DOB
NOR a contact field — only the primary borrower's CustomerId (under
lstCoBorrowers). GetCustomerSearch (mobile) has DOB + CustomerId. So the
three inputs (agreement, mobile, DOB) are cross-checked by comparing the two
calls' CustomerId and the entered DOB against GetCustomerSearch's DOB.
OTP (mobile flow only): 6-digit, 5-min expiry, 3 attempts, 30s resend,
5/hr per mobile."""

import datetime as dt
import re

from django.http import HttpResponseRedirect
from django.shortcuts import render

from portal.i18n import LANGS
from portal.lms import get_lms
from portal.ratelimit import rate_limit
from portal.services import otp_service, session_service
from portal.services.allcloud_auth import LMSError
from portal.services.audit import audit
from portal.services.crypto import mask_mobile
from portal.services.otp_service import OtpError

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
AGREEMENT_RE = re.compile(r"^[A-Z0-9\-]{6,30}$", re.IGNORECASE)

# AllCloud's DOB format is unconfirmed (could be DD-MM-YYYY, with a time
# suffix, etc.) — parse actual dates rather than compare raw strings, or a
# format mismatch silently fails the match even when the DOB is correct.
_DOB_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y")


def _parse_loose_date(value: str) -> dt.date | None:
    if not value:
        return None
    head = re.split(r"[T ]", value.strip(), maxsplit=1)[0]
    for fmt in _DOB_FORMATS:
        try:
            return dt.datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


def _clean_mobile(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits if MOBILE_RE.match(digits) else None


def login_page(request):
    expired = request.GET.get("expired")
    return render(request, "login.html", {"expired": expired})


@rate_limit(10, 3600)
async def send_otp(request):
    """HTMX endpoint: validates mobile against LMS, then sends OTP."""
    mobile = request.POST.get("mobile", "")
    cleaned = _clean_mobile(mobile)
    if not cleaned:
        return render(request, "partials/login_error.html", {"error_key": "err_invalid_mobile"})
    lms = get_lms()
    try:
        customers = await lms.get_customer_search(cleaned)
    except LMSError:
        return render(request, "partials/login_error.html", {"error_key": "err_lms_down"})
    if not customers:
        await audit(request, "login_unknown_mobile", mobile_mask=mask_mobile(cleaned), mobile=cleaned)
        return render(request, "partials/login_error.html", {"error_key": "err_mobile_not_found"})
    try:
        await otp_service.send_otp(cleaned)
    except OtpError as exc:
        return render(request, "partials/login_error.html", {"error_key": exc.code})
    await audit(request, "otp_sent", mobile_mask=mask_mobile(cleaned), mobile=cleaned)
    return render(
        request,
        "partials/otp_form.html",
        {"mobile": cleaned, "mobile_mask": mask_mobile(cleaned), "flow": "mobile"},
    )


@rate_limit(10, 3600)
async def resend_otp(request):
    mobile = request.POST.get("mobile", "")
    flow = request.POST.get("flow", "mobile")
    cleaned = _clean_mobile(mobile)
    if not cleaned:
        return render(request, "partials/login_error.html", {"error_key": "err_invalid_mobile"})
    error_key = None
    try:
        await otp_service.send_otp(cleaned)
        await audit(request, "otp_resent", mobile_mask=mask_mobile(cleaned), mobile=cleaned)
    except OtpError as exc:
        error_key = exc.code
    return render(
        request,
        "partials/otp_form.html",
        {"mobile": cleaned, "mobile_mask": mask_mobile(cleaned), "flow": flow, "error_key": error_key},
    )


@rate_limit(30, 3600)
async def verify_otp(request):
    mobile = request.POST.get("mobile", "")
    otp = request.POST.get("otp", "")
    flow = request.POST.get("flow", "mobile")
    cleaned = _clean_mobile(mobile)
    if not cleaned:
        return render(request, "partials/login_error.html", {"error_key": "err_invalid_mobile"})

    def otp_error(key: str):
        return render(
            request,
            "partials/otp_form.html",
            {"mobile": cleaned, "mobile_mask": mask_mobile(cleaned), "flow": flow, "error_key": key},
        )

    try:
        ok = await otp_service.verify_otp(cleaned, (otp or "").strip())
    except OtpError as exc:
        return otp_error(exc.code)
    if not ok:
        return otp_error("otp_wrong")

    # OTP verified -> build the session with the LMS-derived FinanceId allow-list.
    lms = get_lms()
    try:
        loans = await lms.get_loans_by_mobile(cleaned)
    except LMSError:
        loans = []
    finance_ids = [str(l.finance_id) for l in loans if l.finance_id]
    # GetLoanByMobileNumber's own CustomerName is unreliable (usually blank)
    # — GetLoanAgreementNoAsync's primary borrower name is the accurate
    # source, so fetch it once for the customer's first loan.
    name = ""
    if loans:
        try:
            agr_loans = await lms.get_loan_by_agreement(loans[0].agreement_no)
            match = next(
                (l for l in agr_loans if l.agreement_no.upper() == loans[0].agreement_no.upper()),
                None,
            )
            name = (match.primary_customer_name if match else "") or loans[0].customer_name
        except LMSError:
            name = loans[0].customer_name
    sess = await session_service.create_session(
        cleaned, finance_ids, customer_name=name,
        login_method="mobile_otp" if flow == "mobile" else "agreement_otp",
    )
    agreement_nos = ",".join(l.agreement_no for l in loans if l.agreement_no)
    await audit(request, "login_success", session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile,
                detail=f"loans={agreement_nos}")

    # HTMX client-side redirect to the dashboard.
    response = render(request, "partials/login_success.html", {})
    response.headers["HX-Redirect"] = "/dashboard"
    session_service.set_session_cookie(response, sess.id)
    return response


# --- alternate flow: agreement no. + mobile + DOB, no OTP --------------------

def agreement_page(request):
    return render(request, "login_agreement.html", {})


@rate_limit(10, 3600)
async def agreement_lookup(request):
    agreement_no = (request.POST.get("agreement_no") or "").strip().upper()
    mobile = request.POST.get("mobile", "")
    dob = request.POST.get("dob", "")  # YYYY-MM-DD from <input type=date>
    cleaned_mobile = _clean_mobile(mobile)
    if not AGREEMENT_RE.match(agreement_no) or not cleaned_mobile:
        return render(request, "partials/login_error.html", {"error_key": "err_agreement_not_found"})

    lms = get_lms()
    try:
        loans = await lms.get_loan_by_agreement(agreement_no)
        customers = await lms.get_customer_search(cleaned_mobile)
    except LMSError:
        return render(request, "partials/login_error.html", {"error_key": "err_lms_down"})

    loan = next((l for l in loans if l.agreement_no.upper() == agreement_no), None)
    customer = customers[0] if customers else None
    entered_dob = _parse_loose_date(dob)

    matched = bool(
        loan and customer and customer.customer_id
        and loan.primary_customer_id == customer.customer_id
        and entered_dob and _parse_loose_date(customer.dob) == entered_dob
    )
    if not matched:
        await audit(request, "agreement_login_failed", detail=f"agr={agreement_no}",
                     mobile_mask=mask_mobile(cleaned_mobile), mobile=cleaned_mobile)
        return render(request, "partials/login_error.html", {"error_key": "err_agreement_not_found"})

    # Matched on all three factors -> session created directly, no OTP.
    try:
        loans = await lms.get_loans_by_mobile(cleaned_mobile)
    except LMSError:
        loans = []
    finance_ids = [str(l.finance_id) for l in loans if l.finance_id]
    # `loan` here is already a GetLoanAgreementNoAsync result — its
    # primary_customer_name is reliable, unlike GetLoanByMobileNumber's.
    name = loan.primary_customer_name or customer.customer_name
    sess = await session_service.create_session(
        cleaned_mobile, finance_ids, customer_name=name, login_method="agreement_dob"
    )
    agreement_nos = ",".join(l.agreement_no for l in loans if l.agreement_no) or agreement_no
    await audit(request, "login_success_agreement", session_id=sess.id, mobile=sess.mobile,
                mobile_mask=sess.mobile_mask, detail=f"loans={agreement_nos}")

    response = render(request, "partials/login_success.html", {})
    response.headers["HX-Redirect"] = "/dashboard"
    session_service.set_session_cookie(response, sess.id)
    return response


async def agreement_dispatch(request):
    if request.method == "POST":
        return await agreement_lookup(request)
    return agreement_page(request)


async def logout(request):
    sess = await session_service.load_session(request)
    if sess:
        await session_service.revoke(sess)
        await audit(request, "logout", session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    response = HttpResponseRedirect("/login")
    session_service.clear_session_cookie(response)
    return response


def set_lang(request, code: str):
    response = HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/login")
    if code in LANGS:
        response.set_cookie("lang", code, max_age=365 * 24 * 3600, samesite="Lax")
    return response
