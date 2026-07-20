"""Custom error handlers — the Django equivalent of the FastAPI version's
@app.exception_handler(403) for the IDOR PermissionDenied case."""

from django.shortcuts import render


def forbidden(request, exception=None):
    return render(request, "error.html", {"error_key": "err_forbidden"}, status=403)
