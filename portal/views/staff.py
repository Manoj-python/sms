"""Internal staff login + audit report. Deliberately separate from the
customer OTP flow in auth.py — no shared cookie, no shared session store,
no self-service signup (accounts provisioned via manage.py create_staff_user).
"""

from datetime import timedelta, timezone as dt_timezone

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import render

from portal.decorators import require_staff_session
from portal.models import AuditLog, StaffUser
from portal.services import staff_session_service

IST = dt_timezone(timedelta(hours=5, minutes=30))


def _ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "")


def login_page(request):
    expired = request.GET.get("expired")
    return render(request, "staff_login.html", {"expired": expired, "error": None})


async def login_submit(request):
    # Small fixed-window brute-force guard, mirroring ratelimit.py's
    # approach but kept local — staff login has no i18n/error_key contract
    # to share with the customer-facing rate_limit decorator.
    ip = _ip(request)
    key = f"staff_login_attempts:{ip}"
    attempts = cache.get(key, 0)
    if attempts >= 10:
        return render(request, "staff_login.html", {"error": "Too many attempts. Try again later."}, status=429)

    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    user = await StaffUser.objects.filter(username=username, is_active=True).afirst()
    if user is None or not check_password(password, user.password_hash):
        cache.set(key, attempts + 1, timeout=900)
        return render(request, "staff_login.html", {"error": "Invalid username or password."})

    cache.delete(key)
    sess = await staff_session_service.create_session(username)
    response = HttpResponseRedirect("/staff/report")
    staff_session_service.set_session_cookie(response, sess.id)
    return response


@require_staff_session
async def logout(request, staff):
    await staff_session_service.revoke(staff)
    response = HttpResponseRedirect("/staff/login")
    staff_session_service.clear_session_cookie(response)
    return response


async def login_dispatch(request):
    if request.method == "POST":
        return await login_submit(request)
    return login_page(request)


@require_staff_session
async def report(request, staff):
    """Audit report: logins (OTP + loan-number flow, with the loan numbers
    captured at login time), payment attempts, and receipt/statement
    downloads. See models.AuditLog — `location`/`latitude`/`longitude` are
    filled in asynchronously after each row is written, so they may be
    blank for the most recent minute of activity.

    Mobile numbers are shown unmasked here (an explicit product decision —
    staff need to identify/contact customers from this report) even though
    they're masked everywhere customer-facing. `mobile` is encrypted at
    rest and decrypts automatically via EncryptedCharField; `mobile_mask`
    is the search key since the DB can't filter on encrypted plaintext, and
    is also the display fallback for rows written before `mobile` existed."""
    action_filter = request.GET.get("action", "")
    mobile_filter = request.GET.get("mobile", "").strip()
    page = max(1, int(request.GET.get("page", 1) or 1))
    page_size = 50

    qs = AuditLog.objects.all().order_by("-created_at")
    if action_filter:
        qs = qs.filter(action=action_filter)
    if mobile_filter:
        qs = qs.filter(mobile_mask__icontains=mobile_filter)

    total = await qs.acount()
    rows = [row async for row in qs[(page - 1) * page_size : page * page_size]]

    display_rows = []
    for row in rows:
        maps_url = None
        if row.latitude is not None and row.longitude is not None:
            maps_url = f"https://www.google.com/maps?q={row.latitude},{row.longitude}"
        display_rows.append({
            "created_at_ist": row.created_at.astimezone(IST).strftime("%d-%m-%Y %H:%M:%S"),
            "action": row.action,
            "mobile": row.mobile or row.mobile_mask,
            "detail": row.detail,
            "ip": row.ip,
            "location": row.location,
            "maps_url": maps_url,
        })

    actions = [
        "login_success", "login_success_agreement", "login_unknown_mobile", "agreement_login_failed",
        "qr_generated", "statement_downloaded", "installment_receipt_downloaded",
        "charge_receipt_downloaded", "receipt_downloaded", "logout",
    ]

    return render(request, "staff_report.html", {
        "rows": display_rows, "total": total, "page": page, "page_size": page_size,
        "has_next": page * page_size < total, "has_prev": page > 1,
        "actions": actions, "action_filter": action_filter, "mobile_filter": mobile_filter,
    })
