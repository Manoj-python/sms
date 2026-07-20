"""Ports the FastAPI portal's @app.middleware("http") security_headers
hook: HTTPS-only redirect in prod (behind a TLS-terminating proxy honouring
X-Forwarded-Proto), and the same fixed response headers on every request."""

from django.http import HttpResponse

from portal.config import get_settings


class SecurityHeadersMiddleware:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
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
