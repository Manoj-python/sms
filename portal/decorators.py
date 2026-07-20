"""Shared async view dependencies: the session guard and the server-side
IDOR check applied to every LMS proxy call that takes a FinanceId."""

import functools

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect

from portal.models import PortalSession
from portal.services import session_service, staff_session_service
from portal.services.allcloud_client import AllCloudClient
from portal.services.audit import audit


def require_staff_session(view_func):
    """Same shape as require_session, but for the internal audit report —
    a completely separate cookie/session store, never a customer session."""

    @functools.wraps(view_func)
    async def wrapper(request, *args, **kwargs):
        staff = await staff_session_service.load_session(request)
        if staff is None:
            return HttpResponseRedirect("/staff/login?expired=1")
        return await view_func(request, staff, *args, **kwargs)

    return wrapper


def require_session(view_func):
    """Injects the live PortalSession as the view's second positional arg
    (after request), redirecting to /login?expired=1 if there isn't one —
    the Django equivalent of the FastAPI `Depends(require_session)`."""

    @functools.wraps(view_func)
    async def wrapper(request, *args, **kwargs):
        sess = await session_service.load_session(request)
        if sess is None:
            return HttpResponseRedirect("/login?expired=1")
        return await view_func(request, sess, *args, **kwargs)

    return wrapper


async def assert_loan_access(
    lms: AllCloudClient,
    sess: PortalSession,
    finance_id: str,
    request=None,
) -> None:
    """IDOR enforcement: a customer may only touch FinanceIds mapped to their
    verified mobile. Checked server-side before EVERY LMS proxy call. The
    allow-list is refreshed once from the LMS before rejecting, to cover
    loans booked after login."""
    finance_id = str(finance_id)
    if finance_id in (sess.finance_ids or []):
        return
    loans = await lms.get_loans_by_mobile(sess.mobile)
    fresh_ids = [str(l.finance_id) for l in loans if l.finance_id]
    await session_service.update_finance_ids(sess, fresh_ids)
    if finance_id in fresh_ids:
        return
    await audit(
        "idor_blocked",
        detail=f"finance_id={finance_id}",
        session_id=sess.id,
        mobile_mask=sess.mobile_mask,
        ip=request.META.get("REMOTE_ADDR", "") if request else "",
    )
    raise PermissionDenied("err_forbidden")
