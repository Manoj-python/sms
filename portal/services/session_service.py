"""Server-side sessions referenced by an itsdangerous-signed cookie.

The cookie holds only a signed session id; mobile + FinanceId allow-list live
in the DB (mobile encrypted at rest). 15-minute idle timeout enforced
server-side on every request."""

from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from itsdangerous import BadSignature, URLSafeSerializer

from portal.config import get_settings
from portal.models import PortalSession
from portal.services.crypto import mask_mobile

COOKIE_NAME = "smsq_session"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="portal-session")


async def create_session(
    mobile: str,
    finance_ids: list[str],
    customer_name: str = "",
    login_method: str = "mobile_otp",
) -> PortalSession:
    return await PortalSession.objects.acreate(
        mobile=mobile,
        mobile_mask=mask_mobile(mobile),
        customer_name=customer_name,
        finance_ids=[str(f) for f in finance_ids],
        login_method=login_method,
    )


def set_session_cookie(response: HttpResponse, session_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _serializer().dumps(session_id),
        httponly=True,
        secure=get_settings().is_prod,  # HTTPS-only cookie in prod
        samesite="Lax",
        max_age=get_settings().session_idle_minutes * 60,
    )


def clear_session_cookie(response: HttpResponse) -> None:
    response.delete_cookie(COOKIE_NAME)


async def load_session(request: HttpRequest) -> PortalSession | None:
    """Returns the live session or None (missing, bad signature, revoked,
    or idle past the timeout). Touches last_seen_at on success."""
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        session_id = _serializer().loads(raw)
    except BadSignature:
        return None
    sess = await PortalSession.objects.filter(pk=session_id).afirst()
    if sess is None or sess.revoked:
        return None
    idle_limit = timedelta(minutes=get_settings().session_idle_minutes)
    if timezone.now() - sess.last_seen_at > idle_limit:
        sess.revoked = True
        await sess.asave()
        return None
    sess.last_seen_at = timezone.now()
    await sess.asave()
    return sess


async def update_finance_ids(sess: PortalSession, finance_ids: list[str]) -> None:
    """Refresh the IDOR allow-list from a fresh LMS loans fetch."""
    sess.finance_ids = [str(f) for f in finance_ids]
    await sess.asave()


async def revoke(sess: PortalSession) -> None:
    sess.revoked = True
    await sess.asave()
