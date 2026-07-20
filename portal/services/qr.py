"""QR code image generation for the document-verification badge — see
doc_verify.py for what gets encoded."""

from io import BytesIO

import qrcode


def qr_png(url: str) -> bytes:
    img = qrcode.make(url, border=1)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
