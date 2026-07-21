"""Serves the service worker from the root path (not /static/sw.js) so its
default scope covers the whole origin — a service worker can only control
paths at or below where it's served from, and this portal has pages outside
/static/ that need the cache-first static-asset handling (see static/sw.js).
"""

from pathlib import Path

from django.conf import settings
from django.http import HttpResponse

_SW_PATH = Path(settings.BASE_DIR) / "portal" / "static" / "sw.js"


async def service_worker(request):
    return HttpResponse(_SW_PATH.read_text(encoding="utf-8"), content_type="application/javascript")
