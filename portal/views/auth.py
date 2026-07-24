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

from portal.config import get_settings
from portal.decorators import require_session
from portal.i18n import LANGS
from portal.lms import get_lms
from portal.ratelimit import rate_limit
from portal.services import device_trust_service, multi_lms, otp_service, session_service
from portal.services.allcloud_auth import LMSError
from portal.services.audit import audit
from portal.services.crypto import mask_mobile
from portal.services.otp_service import OtpError

PIN_RE = re.compile(r"^\d{6}$")

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


async def login_page(request):
    """Shows the PIN quick-unlock form instead of the mobile+OTP form when
    this browser carries a valid, non-locked device-trust cookie (see
    device_trust_service) — ?otp=1 always forces the plain mobile form so
    the PIN screen is never a dead end."""
    expired = request.GET.get("expired")
    device = None
    if not request.GET.get("otp"):
        device = await device_trust_service.load_device(request)
    return render(request, "login.html", {
        "expired": expired, "pin_unlock": device is not None,
        "mobile_mask": device.mobile_mask if device else "",
    })


async def _finish_login(request, mobile: str, login_method: str, audit_action: str):
    """Shared tail of every successful login path (OTP, agreement+DOB, PIN
    unlock): derive the FinanceId allow-list from a full cross-tenant scan,
    resolve the customer name, create the session, audit, and return the
    HX-Redirect response with the session cookie set. Kept in ONE place so
    the three flows can't drift apart on the IDOR-critical allow-list
    derivation."""
    tagged_loans = await multi_lms.loans_by_mobile_all_tenants(mobile)
    loans = [loan for _, loan in tagged_loans]
    finance_ids = [str(l.finance_id) for l in loans if l.finance_id]
    finance_lenders = {str(l.finance_id): lender for lender, l in tagged_loans if l.finance_id}
    # GetLoanByMobileNumber's own CustomerName is unreliable (usually blank)
    # — GetLoanAgreementNoAsync's primary borrower name is the accurate
    # source, so fetch it once for the customer's first loan, from whichever
    # tenant that specific loan actually belongs to.
    name = ""
    if tagged_loans:
        first_lender, first_loan = tagged_loans[0]
        try:
            agr_loans = await get_lms(first_lender).get_loan_by_agreement(first_loan.agreement_no)
            match = next(
                (l for l in agr_loans if l.agreement_no.upper() == first_loan.agreement_no.upper()),
                None,
            )
            name = (match.primary_customer_name if match else "") or first_loan.customer_name
        except LMSError:
            name = first_loan.customer_name
    sess = await session_service.create_session(
        mobile, finance_ids, customer_name=name,
        login_method=login_method, finance_lenders=finance_lenders,
    )
    agreement_nos = ",".join(l.agreement_no for l in loans if l.agreement_no)
    await audit(request, audit_action, session_id=sess.id, mobile_mask=sess.mobile_mask,
                mobile=sess.mobile, detail=f"loans={agreement_nos}")

    # HTMX client-side redirect to the dashboard.
    response = render(request, "partials/login_success.html", {})
    response.headers["HX-Redirect"] = "/dashboard"
    session_service.set_session_cookie(response, sess.id)
    return response


@rate_limit(10, 3600)
async def send_otp(request):
    """HTMX endpoint: validates mobile against LMS, then sends OTP."""
    mobile = request.POST.get("mobile", "")
    cleaned = _clean_mobile(mobile)
    if not cleaned:
        return render(request, "partials/login_error.html", {"error_key": "err_invalid_mobile"})
    # SMSquare is checked first (most customers are SMSquare's own); only
    # falls through to Padmasai then Sreemani if SMSquare has no match at
    # all (per explicit product decision) — see find_customer_priority's
    # docstring. This only gates whether an OTP gets sent; once logged in,
    # the dashboard still shows loans from every tenant this mobile
    # actually has one at (see verify_otp below).
    lender, _customer = await multi_lms.find_customer_priority(cleaned)
    if lender is None:
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

    # OTP verified -> shared login tail (full cross-tenant allow-list
    # derivation + session + audit) — see _finish_login.
    return await _finish_login(
        request, cleaned,
        login_method="mobile_otp" if flow == "mobile" else "agreement_otp",
        audit_action="login_success",
    )


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

    # An agreement number belongs to exactly one tenant — first-match-wins
    # search across SMSquare's own portfolio and the two acquired ones.
    lender, loans = await multi_lms.find_agreement_any_tenant(agreement_no)
    if lender is None:
        return render(request, "partials/login_error.html", {"error_key": "err_agreement_not_found"})
    # The mobile cross-check must go to that SAME tenant — a mobile could
    # plausibly exist as an unrelated customer at a different lender, and
    # cross-checking CustomerId against the wrong tenant would be meaningless.
    try:
        customers = await get_lms(lender).get_customer_search(cleaned_mobile)
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

    # Matched on all three factors -> session created directly, no OTP. Even
    # though login started from one tenant's agreement number, the same
    # mobile might hold loans at other lenders too — _finish_login searches
    # all of them so the dashboard shows everything, not just the one they
    # logged in through.
    return await _finish_login(
        request, cleaned_mobile, login_method="agreement_dob", audit_action="login_success_agreement",
    )


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
    # Deliberately does NOT touch the device-trust cookie/DeviceTrust row —
    # PIN quick-unlock is meant to survive a logout (that's the whole
    # point: next visit shows the PIN screen, not the mobile form again).
    # "Forget this device" (pin_disable) is the only thing that revokes it.
    return response


# --- PIN quick-unlock (opt-in device trust) ---------------------------------
# A PIN never re-proves identity from scratch — it only lets a device that
# already completed a real OTP/agreement+DOB login skip OTP on later visits.
# See device_trust_service.py's module docstring for the full security model.


@rate_limit(10, 3600)
async def pin_unlock(request):
    device = await device_trust_service.load_device(request)
    if device is None:
        # Cookie missing/invalid/revoked, or locked out from a prior
        # request (e.g. a concurrent tab already burned the last attempt)
        # — never a dead end, fall back to the normal mobile+OTP form.
        return render(request, "partials/login_mobile_form.html", {})

    pin = (request.POST.get("pin") or "").strip()
    ok = await device_trust_service.verify_pin(device, pin)
    if not ok:
        device = await device_trust_service.load_device(request)  # re-check: verify_pin may have just locked it
        if device is None:
            return render(request, "partials/pin_unlock_form.html", {"locked": True})
        remaining = get_settings().pin_max_attempts - device.failed_attempts
        return render(request, "partials/pin_unlock_form.html", {
            "error_key": "pin_wrong", "remaining": remaining, "mobile_mask": device.mobile_mask,
        })

    return await _finish_login(request, device.mobile, login_method="pin_unlock", audit_action="login_success_pin")


@require_session
async def pin_setup(request, sess):
    """GET renders the "set your PIN" form; POST creates the DeviceTrust
    and sets its cookie. Both are meant to be HTMX-loaded into profile.html's
    #pin-box, matching the rest of the portal's partial-swap pattern."""
    if request.method != "POST":
        return render(request, "partials/pin_setup_form.html", {})

    pin = (request.POST.get("pin") or "").strip()
    confirm = (request.POST.get("pin_confirm") or "").strip()
    if not PIN_RE.match(pin):
        return render(request, "partials/pin_setup_form.html", {"error_key": "err_invalid_pin"})
    if pin != confirm:
        return render(request, "partials/pin_setup_form.html", {"error_key": "pin_confirm_mismatch"})

    device = await device_trust_service.create(sess.mobile, pin)
    await audit(request, "pin_enabled", session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    response = render(request, "partials/pin_setup_form.html", {"success": True})
    device_trust_service.set_device_cookie(response, device.id)
    return response


@require_session
async def pin_disable(request, sess):
    """"Forget this device" — the only thing that revokes a DeviceTrust
    (logout deliberately does not, see logout's comment above)."""
    device = await device_trust_service.load_device(request)
    # mobile match, not just "any device cookie present" — a customer could
    # in principle be looking at this page for a mobile that isn't the one
    # the current browser's device cookie belongs to (e.g. a shared device
    # previously trusted for a different family member's mobile); only ever
    # revoke a device that actually belongs to the mobile they're logged in
    # as right now.
    if device is not None and device.mobile == sess.mobile:
        await device_trust_service.revoke(device)
        await audit(request, "pin_disabled", session_id=sess.id, mobile_mask=sess.mobile_mask, mobile=sess.mobile)
    response = render(request, "partials/pin_setup_form.html", {})
    device_trust_service.clear_device_cookie(response)
    return response


def set_lang(request, code: str):
    response = HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/login")
    if code in LANGS:
        response.set_cookie("lang", code, max_age=365 * 24 * 3600, samesite="Lax")
    return response
