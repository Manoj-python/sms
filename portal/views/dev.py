"""Diagnostics behind /dev/lms-probe: lets an admin inspect raw AllCloud
responses (schemas are undocumented) to tighten lms_schemas.py. Always gated
by ADMIN_PROBE_KEY. In prod, only GET is allowed: POST probes could trigger a
real QR generation, so writes stay UAT/mock-only here."""

import json

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse

from portal.config import get_settings
from portal.lms import get_lms


def _guard(x_admin_key: str | None, method: str):
    s = get_settings()
    if not s.admin_probe_key or x_admin_key != s.admin_probe_key:
        return HttpResponseForbidden("X-Admin-Key required", status=401)
    if s.is_prod and method.upper() != "GET":
        return HttpResponseForbidden("prod probe is GET-only")
    return None


async def lms_probe(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponseBadRequest("invalid JSON body")
    method = body.get("method", "GET")
    path = body.get("path", "")
    probe_body = body.get("body")

    guard_resp = _guard(request.headers.get("X-Admin-Key"), method)
    if guard_resp is not None:
        return guard_resp
    if not path.startswith("/api/"):
        return HttpResponseBadRequest("path must start with /api/")

    lms = get_lms()
    raw = await lms.raw_probe(method, path, probe_body)
    return JsonResponse({"path": path, "raw": raw})
