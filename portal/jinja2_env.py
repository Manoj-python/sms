"""Custom Jinja2 environment for Django's Jinja2 template backend.

Registers the `dmy` date filter, exactly as the FastAPI portal did on its
Jinja2Templates instance in dependencies.py — this lets every template
carry over from the FastAPI version unchanged.
"""

import datetime as dt
import re

from jinja2 import Environment


def dmy(value: str) -> str:
    """Formats an AllCloud date string (YYYY-MM-DD, optionally with a time
    suffix) as dd/mm/yy for display. Returns '—' for blank/unparseable
    input rather than raising, since these dates come from external APIs."""
    if not value:
        return "—"
    head = re.split(r"[T ]", value.strip(), maxsplit=1)[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(head, fmt).strftime("%d/%m/%y")
        except ValueError:
            continue
    return "—"


def environment(**options):
    # Django's Jinja2 backend defaults auto_reload to settings.DEBUG, which
    # is False whenever APP_ENV=prod (real AllCloud credentials) — even
    # though this app has no actual separate production deployment yet, it
    # only ever runs locally. Without this override, template edits stop
    # taking effect at all once switched to prod mode until the server is
    # restarted (confirmed live 2026-07-18 — a WhatsApp icon edit silently
    # never rendered). Force it on unconditionally for now; revisit if this
    # app gets a real production deployment where DEBUG=False actually means
    # "don't touch template files without a redeploy."
    options["auto_reload"] = True
    env = Environment(**options)
    env.filters["dmy"] = dmy
    return env
