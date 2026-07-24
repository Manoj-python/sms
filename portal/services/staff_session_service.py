"""Staff sessions for the internal audit report — deliberately separate
from portal.services.session_service (different cookie, different
signing salt, no customer mobile/OTP involved). Mirrors that module's
signed-cookie + server-side idle-timeout design."""

from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from itsdangerous import BadSignature, URLSafeSerializer

from portal.config import get_settings
from portal.models import StaffSession

COOKIE_NAME = "smsq_staff_session"
IDLE_MINUTES = 30


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="portal-staff-session")


async def create_session(username: str) -> StaffSession:
    return await StaffSession.objects.acreate(username=username)


def set_session_cookie(response: HttpResponse, session_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _serializer().dumps(session_id),
        httponly=True,
        secure=get_settings().is_prod,
        samesite="Lax",
        max_age=IDLE_MINUTES * 60,
    )


def clear_session_cookie(response: HttpResponse) -> None:
    response.delete_cookie(COOKIE_NAME)


async def load_session(request: HttpRequest) -> StaffSession | None:
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        session_id = _serializer().loads(raw)
    except BadSignature:
        return None
    sess = await StaffSession.objects.filter(pk=session_id).afirst()
    if sess is None or sess.revoked:
        return None
    if timezone.now() - sess.last_seen_at > timedelta(minutes=IDLE_MINUTES):
        sess.revoked = True
        await sess.asave()
        return None
    sess.last_seen_at = timezone.now()
    await sess.asave()
    return sess


async def revoke(sess: StaffSession) -> None:
    sess.revoked = True
    await sess.asave()
