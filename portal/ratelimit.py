"""IP-level rate limiting for the login endpoints — the Django equivalent of
the FastAPI version's slowapi `@limiter.limit("10/hour")` decorators.
Fixed-window counter backed by Django's cache framework (LocMemCache by
default — in-process, matching slowapi's own default in-memory storage).

Per-mobile hourly OTP limits are additionally enforced in otp_service
against otp_log, which survives IP rotation — unaffected by this layer.
"""

from functools import wraps

from django.core.cache import cache
from django.shortcuts import render


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "")


def rate_limit(limit: int, period_seconds: int = 3600):
    """On exceeding `limit` calls per `period_seconds` per client IP,
    short-circuits straight to the same 429 response the FastAPI version's
    global RateLimitExceeded handler rendered for every rate-limited route."""

    def decorator(view_func):
        @wraps(view_func)
        async def wrapper(request, *args, **kwargs):
            ip = _client_ip(request)
            key = f"ratelimit:{view_func.__module__}.{view_func.__name__}:{ip}"
            count = cache.get(key, 0)
            if count >= limit:
                return render(
                    request, "partials/login_error.html",
                    {"error_key": "otp_rate_limited"}, status=429,
                )
            cache.set(key, count + 1, timeout=period_seconds)
            return await view_func(request, *args, **kwargs)

        return wrapper

    return decorator
