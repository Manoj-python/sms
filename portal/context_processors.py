"""Injects t/lang/settings into every template render — the Django
equivalent of the FastAPI portal's render() helper building that same base
ctx dict on every call."""

from portal.config import get_settings
from portal.i18n import LANGS, make_translator


def get_lang(request) -> str:
    lang = request.COOKIES.get("lang", "en")
    return lang if lang in LANGS else "en"


def portal_context(request):
    lang = get_lang(request)
    return {"t": make_translator(lang), "lang": lang, "settings": get_settings()}
