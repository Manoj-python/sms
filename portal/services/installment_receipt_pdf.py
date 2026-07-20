"""Per-installment payment receipt ("Customer Copy" voucher), built from
live GetCustomerSearch + GetLoanAgreementNoAsync + GetLccDetailsByAgreementNo
data for one already-paid RepaymentScheduleEntry.

AllCloud's own internal receipt additionally carries a Voucher No.,
Instrument No., Cashier name, and an exact created-at timestamp — none of
these are present on RepaymentSchedules (confirmed live 2026-07-18) or any
other currently-integrated endpoint, so they're shown as "—" rather than
fabricated.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from portal.config import get_settings
from portal.lms_schemas import CustomerSearchResult, LccDetails, LoanSummary, RepaymentScheduleEntry
from portal.services.doc_verify import verify_url
from portal.services.pdf_security import encryption_for
from portal.services.qr import qr_png

IST = timezone(timedelta(hours=5, minutes=30))
NAVY = colors.HexColor("#12355b")
TEAL = colors.HexColor("#0e9494")
LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "img" / "logo.jpeg"
LIGHT = colors.HexColor("#e0f4f4")
GREY = colors.HexColor("#64748b")
GREEN = colors.HexColor("#1a7f37")


def _dmy(value: str) -> str:
    if not value:
        return "-"
    head = value.strip().split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(head, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return value


def _money(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _last_date(value: str) -> str:
    """PaymentDate, like PaidAmount, can be a comma-separated list of dates
    when an installment received multiple partial payments (confirmed live
    2026-07-18) — take the most recent one; a receipt is for one payment
    event, not a list."""
    if not value:
        return "-"
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    return _dmy(parts[-1]) if parts else "-"


def _paid_amount(value: str) -> float:
    """RepaymentScheduleEntry.paid_amount is usually a single numeric
    string, but confirmed live (2026-07-18) AllCloud sometimes packs
    multiple partial receipts against one installment into a single
    comma-separated string (e.g. "3670.00, 126.00") — sum the parts rather
    than crash on a plain float() conversion."""
    if not value:
        return 0.0
    total = 0.0
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            total += float(part)
        except ValueError:
            continue
    return total


def _amount_for_date(entry: RepaymentScheduleEntry, target_date: str) -> float:
    """PaidAmount and PaymentDate are parallel comma-separated lists on the
    same installment (confirmed live 2026-07-18: installment 23 had
    PaidAmount="1998.00, 1672.00" / PaymentDate="06-04-2026, 07-05-2026" —
    index-matched, two separate payments against one installment). Returns
    just the slice paid on target_date, not the installment's full total,
    so a receipt for one voucher doesn't pull in an unrelated earlier
    payment on the same installment."""
    dates = [p.strip() for p in (entry.payment_date or "").split(",") if p.strip()]
    amounts = [p.strip() for p in (entry.paid_amount or "").split(",") if p.strip()]
    if len(dates) != len(amounts):
        # Can't reliably pair mismatched lists — safe fallback: only trust
        # the total when there's just one payment date to begin with.
        return _paid_amount(entry.paid_amount) if len(dates) <= 1 else 0.0
    total = 0.0
    for d, a in zip(dates, amounts):
        if _dmy(d) == target_date:
            try:
                total += float(a)
            except ValueError:
                pass
    return total


def voucher_breakdown(loan: LoanSummary, target_date: str) -> dict:
    """Everything a voucher for `target_date` is made of: EMI slice(s),
    LPC/collection charges, other/bounce VAS charges, and the total. Shared
    by build_installment_receipt_pdf (renders these as line items) and
    receipt_dates (shows the total in the Downloads list) so the
    attribution rules below live in exactly one place.

    A single payment can clear more than one installment in one voucher
    (confirmed live 2026-07-18 against a real AllCloud receipt: one
    transaction paid off the tail of installment 23 AND installment 24
    together) — AllCloud's own receipt is per-voucher, not per-installment.
    Every installment with a slice paid on target_date is grouped into one
    voucher, matching that behaviour.

    LPC/CollectionCharges are single numbers per installment, not
    date-split like PaidAmount/PaymentDate. "Earliest payment date gets the
    LPC" is a best-effort heuristic, not a confirmed rule — validated
    rupee-for-rupee against real receipts across four loans (25/32, 21/24,
    21/23, 6/9 exact matches), and every remaining mismatch traces to this
    same cause: an installment whose LPCReceived was actually collected
    across MORE THAN ONE of its own payment dates. Confirmed live
    2026-07-19/20 that there's no single positional rule — one loan had it
    land on the first date, another on the last, another split across two
    middle dates — and the API never exposes which. Left as the
    earliest-date guess because it's right far more often than not, not
    because it's provably correct.

    Non-EMI charges (app usage fees, postal, UPI NACH bounce, ...) settled
    in the same voucher — confirmed live 2026-07-19 against three real
    receipts: both "OtherCharges" AND "BounceCharges" VAS entries bundle
    into an EMI voucher by ReceivedDate, shown as two separate lines. (A
    due-date-keyed standalone version of the same underlying charge can
    ALSO exist as its own receipt — see build_charge_receipt_pdf — these
    appear to be two different documents about the same charge, not
    duplicates.)

    Known gap: unlike RepaymentSchedules' PaidAmount/PaymentDate, a VAS
    entry that was itself paid across multiple dates only exposes ONE
    ReceivedDate/Amount — there's no comma-split history to divide by date
    the way installment payments have. When that happens the total here
    will be off by whatever slice actually belongs to a different voucher
    (confirmed live: e.g. a 500 bounce charge appearing partly on an
    earlier voucher and partly on a later one) — a real ceiling in the data
    available from GetLoanAgreementNoAsync, not a logic bug.

    A related case (confirmed live 2026-07-19 against two real vouchers,
    loan L2WNAPEGV-240510081): a single voucher that bundles many months of
    bounce charges at once (6-12 VASTypeId="BounceCharges" entries all
    sharing one ReceivedDate) was off by the same 210 in both directions —
    neither ActuallyAmount, ReceivedAmount, nor any other VAS field closes
    that gap, so a bulk bounce-charge settlement voucher can be a few
    hundred rupees off even though a single-charge voucher is exact.

    Also confirmed live 2026-07-20 (loan L2WNAPEGV-240710230): a
    "Receipt Voucher" row in AllCloud's own ledger with NO corresponding
    payment anywhere in RepaymentSchedules is very likely a bounced eNACH
    auto-debit attempt that was later reversed — this function has nothing
    to attribute a total to on that date, correctly returning 0."""
    entries = []
    for e in loan.repayment_schedules:
        amt = _amount_for_date(e, target_date)
        if amt <= 0:
            continue
        dates = [p.strip() for p in (e.payment_date or "").split(",") if p.strip()]
        is_first_payment = (not dates) or (_dmy(dates[0]) == target_date)
        entries.append({
            "installment_no": e.installment_no,
            "due_date": e.due_date,
            "amount": amt,
            "lpc": e.lpc_received if is_first_payment else 0.0,
            "collection": e.collection_charges if is_first_payment else 0.0,
        })
    total_lpc = sum(v["lpc"] for v in entries)
    total_collection = sum(v["collection"] for v in entries)
    other_charges = sum(
        v.amount for v in loan.vas_list
        if "othercharges" in v.vas_type_id.lower().replace(" ", "")
        and "bounce" not in v.name.lower()
        and _dmy(v.received_date) == target_date
    )
    bounce_charges = sum(
        v.amount for v in loan.vas_list
        if "bounce" in v.name.lower()
        and _dmy(v.received_date) == target_date
    )
    total_paid = sum(v["amount"] for v in entries)
    return {
        "entries": entries,
        "total_lpc": total_lpc,
        "total_collection": total_collection,
        "other_charges": other_charges,
        "bounce_charges": bounce_charges,
        "total": total_paid + total_lpc + total_collection + other_charges + bounce_charges,
    }


def receipt_dates(loan: LoanSummary) -> list[dict]:
    """Every distinct date on which any installment received a payment,
    across the whole loan — date-wise, not installment-wise, since one
    voucher can span several installments (see build_installment_receipt_pdf).
    The amount is the full voucher total (EMI + LPC + collection + other/
    bounce charges), matching what the receipt PDF for that date actually
    shows — not just the EMI slice."""
    dates: set[str] = set()
    for e in loan.repayment_schedules:
        for d in (e.payment_date or "").split(","):
            d = d.strip()
            if d:
                dates.add(_dmy(d))
    ordered = sorted(dates, key=lambda d: datetime.strptime(d, "%d-%m-%Y"), reverse=True)
    result = [{"date": d, "amount": voucher_breakdown(loan, d)["total"]} for d in ordered]
    return [r for r in result if r["amount"] > 0]


def _draw_watermark(c: canvas.Canvas, width: float, height: float, text: str) -> None:
    """Faint diagonal brand watermark — a quick visual authenticity marker
    (a genuine receipt is instantly distinguishable from a plain copied
    template) rather than a cryptographic anti-tamper measure."""
    c.saveState()
    c.setFillColor(TEAL)
    c.setFillAlpha(0.07)
    c.setFont("Helvetica-Bold", 34)
    c.translate(width / 2, height / 2 - 10 * mm)
    c.rotate(35)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def _draw_logo(c: canvas.Canvas, x: float, y: float, size: float) -> None:
    """Top-right corner of the letterhead band, opposite the CUSTOMER COPY
    badge. No-op if the logo file isn't present rather than raising."""
    if LOGO_PATH.exists():
        c.drawImage(str(LOGO_PATH), x, y, width=size, height=size, mask="auto")


def _draw_qr(c: canvas.Canvas, x: float, y: float, size: float, url: str) -> None:
    """Bottom-left, above the footer strip — see doc_verify.py."""
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(BytesIO(qr_png(url))), x, y, width=size, height=size)


def _draw_paid_stamp(c: canvas.Canvas, x: float, y: float) -> None:
    """A rotated green ring-stamp — the kind of authenticity flourish a real
    printed receipt carries, distinguishing a genuine paid voucher at a
    glance."""
    c.saveState()
    c.translate(x, y)
    c.rotate(-14)
    c.setStrokeColor(GREEN)
    c.setFillColor(GREEN)
    c.setFillAlpha(0.85)
    c.setLineWidth(1.3)
    c.circle(0, 0, 11 * mm, stroke=1, fill=0)
    c.circle(0, 0, 9 * mm, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(0, 1 * mm, "PAID")
    c.setFont("Helvetica", 5)
    c.drawCentredString(0, -4 * mm, "SMSquare")
    c.restoreState()


def build_installment_receipt_pdf(
    customer: CustomerSearchResult,
    loan: LoanSummary,
    lcc: LccDetails | None,
    installment: RepaymentScheduleEntry,
    target_date: str | None = None,
) -> bytes:
    s = get_settings()
    # A single payment can clear more than one installment in one voucher
    # (confirmed live 2026-07-18 against a real AllCloud receipt: one
    # transaction paid off the tail of installment 23 AND installment 24
    # together) — AllCloud's own receipt is per-voucher, not per-
    # installment. Group every installment that has a slice paid on this
    # same date into one receipt, matching that behaviour.
    #
    # `target_date` (dd-mm-yyyy) lets a caller pick an EARLIER voucher than
    # `installment`'s own most-recent payment date — an installment's
    # PaymentDate list can span several distinct payment events (e.g.
    # "06-04-2026, 07-05-2026"), each its own receipt. See
    # voucher_breakdown()'s docstring for the attribution rules and their
    # documented limits.
    if target_date is None:
        target_date = _last_date(installment.payment_date)
    breakdown = voucher_breakdown(loan, target_date)
    voucher_entries = breakdown["entries"] or [{
        "installment_no": installment.installment_no, "due_date": installment.due_date,
        "amount": _paid_amount(installment.paid_amount), "lpc": 0.0, "collection": 0.0,
    }]
    other_charges = breakdown["other_charges"]
    bounce_charges = breakdown["bounce_charges"]

    buf = BytesIO()
    # A compact voucher, not a full A5 sheet — the content only ever runs to
    # about 110mm tall, so a full A5 (210mm) left a large blank lower half.
    # Grows a little per extra installment when one voucher spans several.
    extra_rows = max(0, len(voucher_entries) - 1) + (1 if other_charges else 0) + (1 if bounce_charges else 0)
    width, height = 148 * mm, (150 + extra_rows * 5.5 + 20) * mm  # +20mm for the verification QR row
    # Password-protected with the customer's own DOB (DDMMYYYY) — see
    # pdf_security.py. Silently unencrypted if DOB is missing/unparseable.
    c = canvas.Canvas(buf, pagesize=(width, height), encrypt=encryption_for(customer.dob))

    margin = 6 * mm
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(1)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    _draw_watermark(c, width, height, "SMSquare")

    # --- navy letterhead band ---
    band_h = 24 * mm
    c.setFillColor(NAVY)
    c.rect(margin, height - margin - band_h, width - 2 * margin, band_h, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(margin, height - margin - band_h, width - 2 * margin, 1.2 * mm, fill=1, stroke=0)

    # "Customer Copy" badge, top-left of the band
    c.setFillColor(TEAL)
    c.roundRect(margin + 2 * mm, height - margin - 6.5 * mm, 24 * mm, 4.5 * mm, 2.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(margin + 14 * mm, height - margin - 5.4 * mm, "CUSTOMER COPY")
    _draw_logo(c, width - margin - 14 * mm, height - margin - 13 * mm, 11 * mm)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, height - margin - 12.5 * mm, s.legal_name)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(width / 2, height - margin - 17.5 * mm, s.company_address.split(".")[0])
    branch = lcc.branch if lcc else "-"
    region = lcc.region if lcc else ""
    branch_line = f"Branch: {branch or '-'}" + (f" ({region})" if region else "")
    c.drawCentredString(width / 2, height - margin - 21.5 * mm, f"{branch_line}   |   Ph: {s.helpline_number}")

    y = height - margin - band_h - 7 * mm

    def label(text, x, yy):
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x, yy, text)

    def value(text, x, yy, bold=False, size=9.5):
        c.setFillColor(NAVY if bold else colors.HexColor("#1c2b3a"))
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, yy, text)

    def row(label_l, value_l, label_r=None, value_r=None, bold_value=False):
        nonlocal y
        label(label_l, margin + 3 * mm, y)
        value(value_l, margin + 26 * mm, y, bold=bold_value)
        if label_r:
            label(label_r, width / 2 + 2 * mm, y)
            value(value_r, width / 2 + 22 * mm, y)
        y -= 6 * mm

    row("Date:", target_date, "Voucher No:", "-")
    row("Customer:", customer.customer_name.title(), bold_value=True)
    vehicle_text = (lcc.registration_no if lcc else "-") or "-"
    if lcc and lcc.vehicle_class:
        vehicle_text += f" ({lcc.vehicle_class})"
    row("Vehicle:", vehicle_text, "Instrument No:", "-")
    row("Ag. Date:", _dmy(loan.start_date), "Ag. No:", loan.agreement_no)
    y -= 1 * mm

    # --- line items table ---
    col_hash, col_due, col_desc, col_amt = margin + 3 * mm, margin + 22 * mm, margin + 48 * mm, width - margin - 4 * mm
    header_h = 6 * mm
    c.setFillColor(NAVY)
    c.rect(margin, y - header_h + 2 * mm, width - 2 * margin, header_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(col_hash, y, "#")
    c.drawString(col_due, y, "Due Date")
    c.drawString(col_desc, y, "Description")
    c.drawRightString(col_amt, y, "Amount")
    y -= 7 * mm

    total_paid = sum(v["amount"] for v in voucher_entries)
    total_lpc = sum(v["lpc"] for v in voucher_entries)
    total_collection = sum(v["collection"] for v in voucher_entries)

    i = 0
    for v in voucher_entries:
        if i % 2:
            c.setFillColor(LIGHT)
            c.rect(margin, y - 3.7 * mm, width - 2 * margin, 5.5 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(col_hash, y, f"(Part) {v['installment_no']} / {loan.duration}")
        c.setFont("Helvetica", 8.5)
        c.drawString(col_due, y, _dmy(v["due_date"]))
        c.setFillColor(colors.HexColor("#1c2b3a"))
        c.drawString(col_desc, y, "EMI")
        c.drawRightString(col_amt, y, _money(v["amount"]))
        y -= 5.5 * mm
        i += 1

    if total_lpc:
        if i % 2:
            c.setFillColor(LIGHT)
            c.rect(margin, y - 3.7 * mm, width - 2 * margin, 5.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1c2b3a"))
        c.setFont("Helvetica", 8.5)
        c.drawString(col_desc, y, "*LP Charges")
        c.drawRightString(col_amt, y, _money(total_lpc))
        y -= 5.5 * mm
        i += 1

    if i % 2:
        c.setFillColor(LIGHT)
        c.rect(margin, y - 3.7 * mm, width - 2 * margin, 5.5 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1c2b3a"))
    c.setFont("Helvetica", 8.5)
    c.drawString(col_desc, y, "Collection Charges")
    c.drawRightString(col_amt, y, _money(total_collection))
    y -= 5.5 * mm
    i += 1

    if other_charges:
        if i % 2:
            c.setFillColor(LIGHT)
            c.rect(margin, y - 3.7 * mm, width - 2 * margin, 5.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1c2b3a"))
        c.setFont("Helvetica", 8.5)
        c.drawString(col_desc, y, "Other Charges")
        c.drawRightString(col_amt, y, _money(other_charges))
        y -= 5.5 * mm
        i += 1

    if bounce_charges:
        if i % 2:
            c.setFillColor(LIGHT)
            c.rect(margin, y - 3.7 * mm, width - 2 * margin, 5.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1c2b3a"))
        c.setFont("Helvetica", 8.5)
        c.drawString(col_desc, y, "Bounce Charges")
        c.drawRightString(col_amt, y, _money(bounce_charges))
        y -= 5.5 * mm

    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.line(margin, y + 2 * mm, width - margin, y + 2 * mm)
    y -= 3 * mm

    # --- total band ---
    total = total_paid + total_lpc + total_collection + other_charges + bounce_charges
    c.setFillColor(TEAL)
    c.setFillAlpha(0.12)
    c.rect(margin, y - 4 * mm, width - 2 * margin, 8 * mm, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawString(margin + 3 * mm, y, "Online Payment")
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(col_amt, y, f"Total  Rs. {_money(total)}")
    y -= 11 * mm

    row("Payment Mode:", installment.payment_mode or "-", "Cashier:", "-")
    y -= 2 * mm
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.line(margin, y, width - margin, y)
    y -= 6 * mm

    c.setFillColor(GREY)
    c.setFont("Helvetica", 7)
    c.drawString(margin + 3 * mm, y, "Customer Signature")
    c.drawRightString(width - margin - 3 * mm, y, f"For {s.legal_name}")
    y -= 8 * mm
    c.drawRightString(width - margin - 3 * mm, y, "Cashier")

    _draw_paid_stamp(c, width / 2 - 10 * mm, y - 2 * mm)

    footer_y = margin + 3 * mm
    # --- verification QR --- see doc_verify.py for what's signed in.
    qr_size = 14 * mm
    qr_y = footer_y + 5 * mm
    _draw_qr(c, margin + 2 * mm, qr_y, qr_size, verify_url("receipt", loan.agreement_no, total, target_date))
    c.setFillColor(GREY)
    c.setFont("Helvetica", 5.5)
    c.drawString(margin + 2 * mm + qr_size + 2 * mm, qr_y + qr_size - 4 * mm, "Scan to verify")
    c.drawString(margin + 2 * mm + qr_size + 2 * mm, qr_y + qr_size - 9 * mm, "this receipt")

    c.setFillColor(GREY)
    c.setFont("Helvetica", 6)
    printed = datetime.now(IST).strftime("%d-%m-%y %H:%M:%S")
    c.drawString(margin + 3 * mm, footer_y, f"Created Date: {target_date}")
    c.drawCentredString(width / 2, footer_y, "This is System Generated Receipt.")
    c.drawRightString(width - margin - 3 * mm, footer_y, printed)

    c.showPage()
    c.save()
    return buf.getvalue()


def build_charge_receipt_pdf(
    customer: CustomerSearchResult,
    loan: LoanSummary,
    lcc: LccDetails | None,
    target_date: str,
) -> bytes:
    """Receipt for standalone UPI NACH bounce charges — a second voucher
    type distinct from build_installment_receipt_pdf. Confirmed live
    2026-07-18: these get settled in a later lump-sum batch (several
    sharing one ReceivedDate months on), but AllCloud's own receipt
    listing dates each occurrence by its own DueDate instead — that's what
    this keys off, not ReceivedDate. Scoped to "bounce" in the name (rather
    than all VASTypeId="OtherCharges") since other OtherCharges entries
    (app usage fees, postal, ...) follow the opposite rule — bundled into
    an EMI voucher by ReceivedDate, see build_installment_receipt_pdf."""
    s = get_settings()
    charges = [
        v for v in loan.vas_list
        if "bounce" in v.name.lower()
        and _dmy(v.due_date) == target_date
    ]

    buf = BytesIO()
    extra_rows = max(0, len(charges) - 1)
    width, height = 148 * mm, (140 + extra_rows * 5.5 + 20) * mm  # +20mm for the verification QR row
    c = canvas.Canvas(buf, pagesize=(width, height), encrypt=encryption_for(customer.dob))

    margin = 6 * mm
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(1)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    _draw_watermark(c, width, height, "SMSquare")

    band_h = 24 * mm
    c.setFillColor(NAVY)
    c.rect(margin, height - margin - band_h, width - 2 * margin, band_h, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(margin, height - margin - band_h, width - 2 * margin, 1.2 * mm, fill=1, stroke=0)

    c.setFillColor(TEAL)
    c.roundRect(margin + 2 * mm, height - margin - 6.5 * mm, 24 * mm, 4.5 * mm, 2.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(margin + 14 * mm, height - margin - 5.4 * mm, "CUSTOMER COPY")
    _draw_logo(c, width - margin - 14 * mm, height - margin - 13 * mm, 11 * mm)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, height - margin - 12.5 * mm, s.legal_name)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(width / 2, height - margin - 17.5 * mm, s.company_address.split(".")[0])
    branch = lcc.branch if lcc else "-"
    region = lcc.region if lcc else ""
    branch_line = f"Branch: {branch or '-'}" + (f" ({region})" if region else "")
    c.drawCentredString(width / 2, height - margin - 21.5 * mm, f"{branch_line}   |   Ph: {s.helpline_number}")

    y = height - margin - band_h - 7 * mm

    def label(text, x, yy):
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x, yy, text)

    def value(text, x, yy, bold=False, size=9.5):
        c.setFillColor(NAVY if bold else colors.HexColor("#1c2b3a"))
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, yy, text)

    def row(label_l, value_l, label_r=None, value_r=None, bold_value=False):
        nonlocal y
        label(label_l, margin + 3 * mm, y)
        value(value_l, margin + 26 * mm, y, bold=bold_value)
        if label_r:
            label(label_r, width / 2 + 2 * mm, y)
            value(value_r, width / 2 + 22 * mm, y)
        y -= 6 * mm

    row("Date:", target_date, "Voucher No:", "-")
    row("Customer:", customer.customer_name.title(), bold_value=True)
    vehicle_text = (lcc.registration_no if lcc else "-") or "-"
    if lcc and lcc.vehicle_class:
        vehicle_text += f" ({lcc.vehicle_class})"
    row("Vehicle:", vehicle_text, "Instrument No:", "-")
    row("Ag. Date:", _dmy(loan.start_date), "Ag. No:", loan.agreement_no)
    y -= 1 * mm

    col_desc, col_amt = margin + 3 * mm, width - margin - 4 * mm
    header_h = 6 * mm
    c.setFillColor(NAVY)
    c.rect(margin, y - header_h + 2 * mm, width - 2 * margin, header_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(col_desc, y, "Description")
    c.drawRightString(col_amt, y, "Amount")
    y -= 7 * mm

    for i, ch in enumerate(charges):
        if i % 2:
            c.setFillColor(LIGHT)
            c.rect(margin, y - 3.7 * mm, width - 2 * margin, 5.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1c2b3a"))
        c.setFont("Helvetica", 8.5)
        c.drawString(col_desc, y, ch.name or ch.vas_type_id)
        c.drawRightString(col_amt, y, _money(ch.amount))
        y -= 5.5 * mm

    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.line(margin, y + 2 * mm, width - margin, y + 2 * mm)
    y -= 3 * mm

    total = sum(ch.amount for ch in charges)
    c.setFillColor(TEAL)
    c.setFillAlpha(0.12)
    c.rect(margin, y - 4 * mm, width - 2 * margin, 8 * mm, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawString(margin + 3 * mm, y, "Online Payment")
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(col_amt, y, f"Total  Rs. {_money(total)}")
    y -= 11 * mm

    row("Payment Mode:", "-", "Cashier:", "-")
    y -= 2 * mm
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.line(margin, y, width - margin, y)
    y -= 6 * mm

    c.setFillColor(GREY)
    c.setFont("Helvetica", 7)
    c.drawString(margin + 3 * mm, y, "Customer Signature")
    c.drawRightString(width - margin - 3 * mm, y, f"For {s.legal_name}")
    y -= 8 * mm
    c.drawRightString(width - margin - 3 * mm, y, "Cashier")

    _draw_paid_stamp(c, width / 2 - 10 * mm, y - 2 * mm)

    footer_y = margin + 3 * mm
    # --- verification QR --- see doc_verify.py for what's signed in.
    qr_size = 14 * mm
    qr_y = footer_y + 5 * mm
    _draw_qr(c, margin + 2 * mm, qr_y, qr_size, verify_url("charge_receipt", loan.agreement_no, total, target_date))
    c.setFillColor(GREY)
    c.setFont("Helvetica", 5.5)
    c.drawString(margin + 2 * mm + qr_size + 2 * mm, qr_y + qr_size - 4 * mm, "Scan to verify")
    c.drawString(margin + 2 * mm + qr_size + 2 * mm, qr_y + qr_size - 9 * mm, "this receipt")

    c.setFillColor(GREY)
    c.setFont("Helvetica", 6)
    printed = datetime.now(IST).strftime("%d-%m-%y %H:%M:%S")
    c.drawString(margin + 3 * mm, footer_y, f"Created Date: {target_date}")
    c.drawCentredString(width / 2, footer_y, "This is System Generated Receipt.")
    c.drawRightString(width - margin - 3 * mm, footer_y, printed)

    c.showPage()
    c.save()
    return buf.getvalue()
