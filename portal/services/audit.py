"""Append-only audit trail.

`mobile` is stored encrypted at rest and shown unmasked on the internal
staff audit report (staff need to identify/contact customers from it — an
explicit product decision, not the original design). `mobile_mask` is kept
alongside for display fallback on rows written before `mobile` existed.

Location: the customer's device (browser Geolocation API, permission-
gated — see device_geo.py and static/js/app.js) is preferred whenever
they've granted it; when they haven't (denied, unsupported, or simply
hasn't answered the prompt yet), this falls back to the existing IP-based
lookup (geoip.py) so there's still a best-effort location either way.

Async (views are async throughout, matching the original httpx-async LMS
client) — call sites must `await audit(...)`."""

import asyncio

from portal.models import AuditLog
from portal.services.device_geo import read_device_geo
from portal.services.geoip import lookup_location

# Location enrichment happens after the row is written, in a background
# task the caller never awaits — a third-party geo lookup must never add
# latency to the login/download/payment request that triggered the audit
# event. Tasks are kept referenced here only so asyncio doesn't garbage-
# collect them mid-flight; each removes itself on completion.
_background_tasks: set[asyncio.Task] = set()


async def _fill_location(row_id: int, ip: str) -> None:
    geo = await lookup_location(ip)
    if geo.location:
        await AuditLog.objects.filter(id=row_id).aupdate(
            location=geo.location, latitude=geo.latitude, longitude=geo.longitude,
        )


async def audit(
    request,
    action: str,
    detail: str = "",
    session_id: str = "",
    mobile_mask: str = "",
    mobile: str = "",
) -> None:
    ip = request.META.get("REMOTE_ADDR", "") if request is not None else ""
    device_geo = read_device_geo(request) if request is not None else None

    row_kwargs = dict(
        session_id=session_id,
        mobile_mask=mobile_mask,
        mobile=mobile,
        action=action,
        detail=detail[:2000],
        ip=ip,
    )
    if device_geo is not None:
        lat, lon = device_geo
        row_kwargs.update(location="Device location (customer-permitted)", latitude=lat, longitude=lon)
    row = await AuditLog.objects.acreate(**row_kwargs)

    # Only fall back to the IP-based lookup when the device didn't already
    # give us a real location — no point overwriting a precise GPS fix
    # with a coarser IP-block guess.
    if ip and device_geo is None:
        task = asyncio.create_task(_fill_location(row.id, ip))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
