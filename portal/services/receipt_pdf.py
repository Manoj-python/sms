"""Payment receipt PDF via reportlab: letterhead, receipt no., UTR and the
full allocation break-up (RBI penal-charges disclosure carried through)."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from portal.config import get_settings
from portal.models import PgTransaction

NAVY = colors.HexColor("#12355b")
TEAL = colors.HexColor("#0e9494")


def build_receipt_pdf(txn: PgTransaction, customer_name: str = "") -> bytes:
    s = get_settings()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # --- letterhead ---
    c.setFillColor(NAVY)
    c.rect(0, height - 30 * mm, width, 30 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, height - 15 * mm, "SMSquare Credit Services")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 21 * mm, "Vehicle Finance | NBFC")
    c.setFillColor(TEAL)
    c.rect(0, height - 32 * mm, width, 2 * mm, fill=1, stroke=0)

    # --- title + meta ---
    y = height - 45 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "PAYMENT RECEIPT")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    meta = [
        ("Receipt No.", txn.receipt_no or "-"),
        ("Date", f"{txn.updated_at:%d-%b-%Y %H:%M}"),
        ("Customer", customer_name or "-"),
        ("Agreement No.", txn.agreement_no or "-"),
        ("Finance ID", txn.finance_id),
        ("UTR / Payment Ref", txn.utr or txn.idempotency_key),
        ("Payment Mode", "UPI"),
    ]
    y -= 10 * mm
    for label, value in meta:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(65 * mm, y, str(value))
        y -= 6 * mm

    # --- allocation break-up ---
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawString(20 * mm, y, "Allocation Break-up")
    y -= 8 * mm
    rows = [
        ("EMI / Principal amount", float(txn.amount)),
        ("Penal charges (LPI)", float(txn.lpi_amount)),
        ("Collection charges", float(txn.collection_charges)),
        ("Discount", -float(txn.discount_amount)),
    ]
    c.setFillColor(colors.black)
    for label, value in rows:
        if label == "Discount" and value == 0:
            continue
        c.setFont("Helvetica", 10)
        c.drawString(25 * mm, y, label)
        c.drawRightString(170 * mm, y, f"Rs. {value:,.2f}")
        y -= 6 * mm
    c.setStrokeColor(TEAL)
    c.line(20 * mm, y + 2 * mm, 175 * mm, y + 2 * mm)
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(25 * mm, y, "Total Received")
    c.drawRightString(170 * mm, y, f"Rs. {float(txn.total_amount):,.2f}")

    # --- footer ---
    y -= 14 * mm
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawString(20 * mm, 22 * mm, f"Grievance: {s.grievance_officer} | {s.grievance_email} | {s.grievance_phone}")
    c.drawString(20 * mm, 17 * mm, f"RBI Ombudsman: {s.ombudsman_url}")
    c.drawString(20 * mm, 12 * mm, "This is a system-generated receipt and does not require a signature.")

    c.showPage()
    c.save()
    return buf.getvalue()
