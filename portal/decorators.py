"""Shared async view dependencies: the session guard and the server-side
IDOR check applied to every LMS proxy call that takes a FinanceId."""

import functools

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect

from portal.models import PortalSession
from portal.services import blocked_loans_service, multi_lms, session_service, staff_session_service
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
    sess: PortalSession,
    finance_id: str,
    request=None,
) -> None:
    """IDOR enforcement: a customer may only touch FinanceIds mapped to their
    verified mobile. Checked server-side before EVERY LMS proxy call. The
    allow-list is refreshed once — searching every AllCloud tenant, since a
    loan may belong to SMSquare's own portfolio or either acquired one (see
    multi_lms.py) — before rejecting, to cover loans booked after login."""
    finance_id = str(finance_id)
    if finance_id not in (sess.finance_ids or []):
        tagged_loans = await multi_lms.loans_by_mobile_all_tenants(sess.mobile)
        fresh_ids = [str(l.finance_id) for _, l in tagged_loans if l.finance_id]
        fresh_lenders = {str(l.finance_id): lender for lender, l in tagged_loans if l.finance_id}
        await session_service.update_finance_ids(sess, fresh_ids, fresh_lenders)
        if finance_id not in fresh_ids:
            await audit(
                request, "idor_blocked",
                detail=f"finance_id={finance_id}",
                session_id=sess.id,
                mobile_mask=sess.mobile_mask,
            )
            raise PermissionDenied("err_forbidden")

    # Ownership confirmed (either already known or just refreshed above) —
    # now check the staff-managed deny-list (see models.BlockedLoan). This
    # is a SEPARATE control from IDOR: the customer genuinely owns this
    # loan, but ops has specifically cut off portal access to it.
    lender = sess.finance_lenders.get(finance_id, "smsquare")
    if await blocked_loans_service.is_blocked(finance_id, lender):
        await audit(
            request, "loan_access_blocked",
            detail=f"finance_id={finance_id}",
            session_id=sess.id,
            mobile_mask=sess.mobile_mask,
        )
        # Per explicit product decision: the "access restricted, contact
        # us" message is only shown when EVERY loan the customer holds is
        # blocked. While they still have at least one usable loan, a
        # blocked one behaves as if it simply doesn't exist — the
        # dashboard already omits it, and a direct URL (old bookmark,
        # stale tab) silently lands back on the dashboard (see errors.py's
        # loan_blocked_partial branch) instead of announcing the block.
        pairs = [(fid, sess.finance_lenders.get(fid, "smsquare")) for fid in (sess.finance_ids or [])]
        blocked_set = await blocked_loans_service.blocked_finance_ids(pairs)
        all_blocked = all(fid in blocked_set for fid, _ in pairs)
        raise PermissionDenied("loan_blocked" if all_blocked else "loan_blocked_partial")
