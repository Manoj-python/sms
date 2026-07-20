"""Wires the framework-agnostic AllCloudClient into Django: a process-wide
singleton client, and a fire-and-forget async log sink writing to
lms_api_log (mirrors the FastAPI version's per-request short-lived DB
session — here as a background task so a slow log write never blocks the
LMS response path)."""

import asyncio
import logging

from portal.models import LmsApiLog
from portal.services.allcloud_client import AllCloudClient

logger = logging.getLogger("portal")


def lms_log_sink(entry: dict) -> None:
    async def _write():
        try:
            await LmsApiLog.objects.acreate(**entry)
        except Exception:
            logger.exception("lms_api_log sink failed")

    try:
        asyncio.get_running_loop().create_task(_write())
    except RuntimeError:
        pass  # no running event loop — drop the log entry rather than block


_client: AllCloudClient | None = None


def get_lms() -> AllCloudClient:
    global _client
    if _client is None:
        _client = AllCloudClient(log_sink=lms_log_sink)
    return _client


async def aclose_lms() -> None:
    if _client is not None:
        await _client.aclose()
