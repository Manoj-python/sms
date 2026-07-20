"""Best-effort IP -> city/region/country + coordinates lookup for the staff
audit report.

Uses ip-api.com's free endpoint (no key, no HTTPS on the free tier — the
payload is non-sensitive, just a city/region/country string and
approximate lat/lon). This sends the customer's IP address to a third
party; only call it from a background task (see audit()), never inline in
a customer-facing request path, and never for private/loopback addresses.
"""

import ipaddress
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("portal.geoip")

_TIMEOUT = 3.0


@dataclass
class GeoResult:
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


async def lookup_location(ip: str) -> GeoResult:
    """Never raises — this is enrichment, not a critical path. Coordinates
    from ip-api.com's free tier are IP-block-level, not GPS-precise — good
    enough for "which city/area", not for a street address."""
    if not ip or not _is_public(ip):
        return GeoResult()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,city,regionName,country,lat,lon"},
            )
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("geoip lookup failed for %s: %s", ip, exc)
        return GeoResult()
    if data.get("status") != "success":
        return GeoResult()
    parts = [p for p in (data.get("city"), data.get("regionName"), data.get("country")) if p]
    return GeoResult(
        location=", ".join(parts),
        latitude=data.get("lat"),
        longitude=data.get("lon"),
    )
