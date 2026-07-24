"""Receives the customer's device-provided coordinates (browser Geolocation
API, only ever called client-side after the browser's own permission
prompt — see static/js/app.js) and stores them in a cookie audit() reads
on every subsequent request. No @require_session: this fires as early as
the login page, before any session exists.
"""

from django.http import HttpResponse

from portal.services.device_geo import set_device_geo_cookie

# 1x1 transparent GIF — this endpoint is hit via `new Image().src = ...`
# (see app.js), so the response needs to be a valid, tiny image, not JSON.
_PIXEL = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def device_location(request):
    try:
        lat = float(request.GET.get("lat", ""))
        lon = float(request.GET.get("lon", ""))
    except ValueError:
        return HttpResponse(_PIXEL, content_type="image/gif")
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        response = HttpResponse(_PIXEL, content_type="image/gif")
        set_device_geo_cookie(response, lat, lon)
        return response
    return HttpResponse(_PIXEL, content_type="image/gif")
