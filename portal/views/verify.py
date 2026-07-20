"""Public document-verification page — reached by scanning the QR code
embedded in downloaded PDFs (see doc_verify.py). Deliberately has no
@require_session: this is meant to be scanned and checked by anyone
(the customer, a bank, an RTO, a field agent), not just a logged-in
customer."""

from django.shortcuts import render

from portal.services.doc_verify import DOC_LABELS, verify_token


def verify_document(request, token: str):
    data = verify_token(token)
    if data is None:
        return render(request, "verify.html", {"valid": False})
    return render(request, "verify.html", {
        "valid": True,
        "doc_label": DOC_LABELS.get(data.get("doc"), data.get("doc")),
        "agreement_no": data.get("agr"),
        "amount": data.get("amt"),
        "doc_date": data.get("date"),
        "generated_at": data.get("gen"),
    })
