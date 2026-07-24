"""Root URL configuration for the SMSquare Customer Portal."""

from django.conf import settings
from django.urls import include, path
from django.views.static import serve

urlpatterns = [
    path("", include("portal.urls")),
    # Served unconditionally (matching the FastAPI version's unconditional
    # app.mount("/static", ...)) — there's no reverse proxy in front of this
    # app yet. Swap for proxy-served static/ once one exists.
    path("static/<path:path>", serve, {"document_root": settings.STATICFILES_DIRS[0]}),
]

# The Django equivalent of the FastAPI version's @app.exception_handler(403)
# for the IDOR PermissionDenied case.
handler403 = "portal.views.errors.forbidden"
