"""Ports the FastAPI portal's @app.middleware("http") security_headers
hook: HTTPS-only redirect in prod (behind a TLS-terminating proxy honouring
X-Forwarded-Proto), and the same fixed response headers on every request."""

import asyncio
import logging

from django.http import HttpResponse

from portal.config import get_settings

logger = logging.getLogger("portal")

# Fire once per process: pre-establish a TCP+TLS connection to each AllCloud
# tenant before a customer's own request needs one. Done here (the one
# request-scoped hook that's guaranteed to run on the SAME event loop uvicorn
# actually serves requests on) rather than at Django app startup — this
# server's ASGI lifespan isn't wired up ("ASGI 'lifespan' protocol appears
# unsupported" in the startup logs), so there's no safe place to run async
# setup before the first real request anyway. Fire-and-forget: runs
# concurrently with the request that triggered it, never blocks or fails it.
_warmed_up = False


def _warm_lms_connections() -> None:
    global _warmed_up
    if _warmed_up:
        return
    _warmed_up = True

    async def _warm_one(lender: str) -> None:
        from portal.lms import get_lms
        try:
            # Cheapest real call available — a mobile that (almost
            # certainly) doesn't exist anywhere still opens the same
            # connection a genuine customer lookup would.
            await get_lms(lender).get_customer_search(
                "0000000000", retry_on_5xx=False, timeout_seconds=get_settings().lms_discovery_timeout_seconds,
            )
        except Exception:
            pass  # best-effort warmup only — a real request retries properly on its own

    for lender in ("smsquare", "padmasai", "sreemani"):
        asyncio.create_task(_warm_one(lender))
    logger.info("LMS connection warmup fired for all 3 tenants")


class SecurityHeadersMiddleware:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        _warm_lms_connections()
        s = get_settings()
        if s.is_prod and request.META.get("HTTP_X_FORWARDED_PROTO", "https") == "http":
            url = request.build_absolute_uri().replace("http://", "https://", 1)
            return HttpResponse(status=308, headers={"Location": url})

        response = await self.get_response(request)
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "no-referrer"
        response["Cache-Control"] = "no-store"  # dues are live; never cache pages
        if s.is_prod:
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
