"""Customer-device geolocation (browser Geolocation API, permission-gated),
preferred over the IP-based fallback in geoip.py whenever the customer has
granted it. See views/geo.py for how the coordinates get here, and
static/js/app.js for the client-side permission request.

Stored as a short-lived cookie (not the session/DB) so it works even
before a customer session exists (e.g. during the login flow, before OTP
is verified) and needs no new table."""

from django.http import HttpRequest, HttpResponse

COOKIE_NAME = "device_geo"
MAX_AGE_SECONDS = 3600  # re-requested by the client on each fresh page load anyway


def set_device_geo_cookie(response: HttpResponse, lat: float, lon: float) -> None:
    # Deliberately NOT httponly — app.js reads this to skip re-requesting
    # the Geolocation permission/fix on every page navigation (each call
    # has a real battery/latency cost, worth avoiding on the budget phones
    # this portal is built for). Just approximate coordinates, not
    # sensitive enough on its own to warrant JS-inaccessibility.
    #
    # Uses ":" rather than "," between lat/lon — a comma in a cookie value
    # triggers automatic RFC 2109 quoting in Python's http.cookies (and
    # Django's own parser round-trips that correctly), but not every
    # browser's cookie handling is guaranteed to agree, especially on the
    # older/budget Android WebViews this portal targets — simplest to just
    # avoid the special character entirely.
    response.set_cookie(
        COOKIE_NAME,
        f"{lat:.6f}:{lon:.6f}",
        max_age=MAX_AGE_SECONDS,
        httponly=False,
        samesite="Lax",
    )


def read_device_geo(request: HttpRequest) -> tuple[float, float] | None:
    raw = request.COOKIES.get(COOKIE_NAME, "")
    if not raw or ":" not in raw:
        return None
    lat_s, _, lon_s = raw.partition(":")
    try:
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon
