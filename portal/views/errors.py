"""Custom error handlers — the Django equivalent of the FastAPI version's
@app.exception_handler(403) for the IDOR PermissionDenied case."""

from django.http import HttpResponseRedirect
from django.shortcuts import render


def forbidden(request, exception=None):
    # assert_loan_access (decorators.py) raises PermissionDenied with a
    # distinguishing message: "loan_blocked" when EVERY loan the customer
    # holds is staff-blocked (show the contact-us message),
    # "loan_blocked_partial" when only SOME are (per explicit product
    # decision, never announce a partial block — the blocked loan behaves
    # as if it doesn't exist, so a direct URL just lands back on the
    # dashboard where the remaining loans work normally), and the plain
    # IDOR case (customer doesn't own this finance_id at all) otherwise.
    reason = str(exception)
    if reason == "loan_blocked_partial":
        return HttpResponseRedirect("/dashboard")
    error_key = "loan_blocked" if reason == "loan_blocked" else "err_forbidden"
    return render(request, "error.html", {"error_key": error_key}, status=403)
