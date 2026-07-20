"""Loan statement-of-account PDF, built from live GetCustomerSearch +
GetLoanAgreementNoAsync data.

Built from the two currently-integrated identity/loan-detail endpoints only
— there is no confirmed separate "statement" endpoint. AllCloud's own
internal statement export additionally shows collateral details (vehicle
make/class/registration/engine/chassis), dealer/invoice info, and a flat
debit-credit transaction journal — none of that is available from these two
endpoints, so this statement omits those sections rather than fabricate
them. The per-installment repayment schedule (due/paid amounts, dates,
modes, LPC) stands in for the transaction journal — it's the closest
confirmed-live equivalent.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from portal.config import get_settings
from portal.lms_schemas import CustomerSearchResult, LccDetails, LoanSummary
from portal.services.doc_verify import verify_url
from portal.services.pdf_security import encryption_for
from portal.services.qr import qr_png

IST = timezone(timedelta(hours=5, minutes=30))
NAVY = colors.HexColor("#12355b")
TEAL = colors.HexColor("#0e9494")
LIGHT = colors.HexColor("#e0f4f4")
GREY = colors.HexColor("#64748b")
LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "img" / "logo.jpeg"


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


def _paid_amount(value: str) -> float:
    """RepaymentScheduleEntry.paid_amount is usually a single numeric
    string, but confirmed live (2026-07-18) AllCloud sometimes packs
    multiple partial receipts against one installment into a single
    comma-separated string (e.g. "3670.00, 126.00") — sum the parts rather
    than crash on the plain float() conversion."""
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


def _last_date(value: str) -> str:
    """PaymentDate, like PaidAmount, can be a comma-separated list of dates
    when an installment received multiple partial payments (confirmed live
    2026-07-18, e.g. "25-05-2024, 28-05-2024") — take the most recent one,
    matching the "Last Receipt Date" column's own name. A plain Table cell
    doesn't wrap, so leaving the full list in would overflow into the next
    column."""
    if not value:
        return "-"
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    return _dmy(parts[-1]) if parts else "-"


def build_statement_pdf(
    customer: CustomerSearchResult, loan: LoanSummary, lcc: LccDetails | None = None,
) -> bytes:
    s = get_settings()
    buf = BytesIO()
    # Password-protected with the customer's own DOB (DDMMYYYY) — standard
    # practice for financial statements. Silently unencrypted if DOB is
    # missing/unparseable rather than locking the customer out with a
    # guessed password.
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
        encrypt=encryption_for(customer.dob),
    )
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=9, textColor=GREY)
    value_style = ParagraphStyle("value", parent=styles["Normal"], fontSize=10, textColor=colors.black)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, textColor=NAVY, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, textColor=NAVY, spaceBefore=10, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GREY)

    def kv(label: str, value: str) -> str:
        return f"<font color='#64748b' size=8>{label}</font><br/><font size=10>{value or '-'}</font>"

    story = []

    # --- letterhead ---
    letterhead_text = [Paragraph(s.legal_name, h1), Paragraph(s.company_address, small)]
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=16 * mm, height=16 * mm)
        letterhead = Table([[logo, letterhead_text]], colWidths=[18 * mm, 152 * mm])
        letterhead.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(letterhead)
    else:
        story.extend(letterhead_text)
    story.append(Spacer(1, 6))
    story.append(Paragraph("STATEMENT OF ACCOUNT", ParagraphStyle(
        "title", parent=styles["Heading1"], fontSize=13, textColor=colors.white,
        backColor=NAVY, alignment=1, spaceAfter=0, borderPadding=6,
    )))
    story.append(Spacer(1, 4))
    generated = datetime.now(IST).strftime("%d-%m-%Y %H:%M")
    story.append(Paragraph(
        f"Loan Number: <b>{loan.agreement_no}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Generated On: {generated} IST",
        small,
    ))
    story.append(Spacer(1, 10))

    # --- borrower + loan details (two columns) ---
    story.append(Paragraph("Borrower Details", h2))
    borrower_rows = [
        [Paragraph(kv("Name", customer.customer_name.title()), value_style),
         Paragraph(kv("Loan No.", loan.agreement_no), value_style)],
        [Paragraph(kv("Father's / Spouse Name", customer.father_name.title()), value_style),
         Paragraph(kv("Loan Date", _dmy(loan.start_date)), value_style)],
        [Paragraph(kv("Mobile No.", customer.contact), value_style),
         Paragraph(kv("Loan Amount", f"Rs. {_money(loan.loan_amount)}"), value_style)],
        [Paragraph(kv("Email ID", customer.email.lower()), value_style),
         Paragraph(kv("Loan Status", loan.disbursement_status), value_style)],
        [Paragraph(kv("Address", customer.full_address), value_style),
         Paragraph(kv(
             "Branch (Region)",
             ((lcc.branch if lcc else "") or "-") + (f" ({lcc.region})" if lcc and lcc.region else ""),
         ), value_style)],
        [Paragraph(kv(
            "Vehicle",
            ((lcc.registration_no if lcc else "") or "-") + (f" ({lcc.vehicle_class})" if lcc and lcc.vehicle_class else ""),
        ), value_style), ""],
    ]
    t = Table(borrower_rows, colWidths=[90 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)

    # --- loan terms + due details (two columns) ---
    story.append(Paragraph("Loan Terms &amp; Due Details", h2))
    installments_paid = round(loan.no_of_paid_emi)
    total_dues = round(loan.overdue_amount + loan.lpi_dues + loan.total_vas_dues, 2)
    terms_rows = [
        [Paragraph(kv("ROI (%) | APR (%)", f"{loan.yearly_indicative_roi:.2f} | {loan.effective_apr:.2f}"), value_style),
         Paragraph(kv("Installments Paid | Total", f"{installments_paid} | {loan.duration}"), value_style)],
        [Paragraph(kv("Installment Amount", f"Rs. {_money(loan.regular_emi_amount)}"), value_style),
         Paragraph(kv("Overdue Installments", f"{loan.emi_due_count:.2f}"), value_style)],
        [Paragraph(kv("Tenure (months)", str(loan.duration)), value_style),
         Paragraph(kv("EMI Due", f"Rs. {_money(loan.overdue_amount)}"), value_style)],
        [Paragraph(kv("Installment Start | End Date", f"{_dmy(loan.emi_start_date)} | {_dmy(loan.emi_end_date)}"), value_style),
         Paragraph(kv("Total Dues", f"Rs. {_money(total_dues)}"), value_style)],
        [Paragraph(kv("Frequency | Last Paid Date", f"{loan.installment_type_id or '-'} | {_dmy(loan.last_paid_date)}"), value_style),
         Paragraph(kv("Charges Dues | LPC Dues", f"Rs. {_money(loan.total_vas_dues)} | Rs. {_money(loan.lpi_dues)}"), value_style)],
        [Paragraph(kv("Repayment Mode", loan.mode_of_repayment_id), value_style),
         Paragraph(kv("Next Due Date", _dmy(loan.next_due_date)), value_style)],
    ]
    t = Table(terms_rows, colWidths=[90 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)

    # --- guarantor(s) ---
    if loan.guarantors:
        story.append(Paragraph("Guarantor(s)", h2))
        g_rows = [["Name", "Relation to Borrower"]]
        for g in loan.guarantors:
            g_rows.append([g.borrower_name.title(), g.entity_type_id])
        gt = Table(g_rows, colWidths=[120 * mm, 60 * mm])
        gt.setStyle(_table_style())
        story.append(gt)

    # --- repayment schedule ---
    # Column layout matches AllCloud's own admin-panel EMI-schedule table
    # (#/EMI/Date/EMI Received/Last Receipt Date/LPI/Discount/LPI Due), incl.
    # a totals row. "Discount" isn't a field RepaymentSchedules returns for
    # any installment (confirmed live 2026-07-18) — shown as 0.00 (a true
    # zero, not a guess) rather than fabricated or omitted, matching every
    # row of the reference table too.
    story.append(Paragraph("Repayment Schedule", h2))
    sched_rows = [["#", "EMI", "Date", "EMI Received", "Last Receipt Date", "LPI", "Discount", "LPI Due"]]
    total_emi = total_received = total_lpi = total_lpi_due = 0.0
    for e in loan.repayment_schedules:
        received = _paid_amount(e.paid_amount)
        sched_rows.append([
            str(e.installment_no), _money(e.due_amount), _dmy(e.due_date),
            _money(received) if received else "-",
            _last_date(e.payment_date),
            _money(e.lpc_received) if e.lpc_received else "-",
            "0.00", _money(e.lpc),
        ])
        total_emi += e.due_amount
        total_received += received
        total_lpi += e.lpc_received
        total_lpi_due += e.lpc
    sched_rows.append([
        "", _money(total_emi), "", _money(total_received), "",
        _money(total_lpi), "0.00", _money(total_lpi_due),
    ])
    st = Table(sched_rows, colWidths=[10 * mm, 20 * mm, 22 * mm, 24 * mm, 30 * mm, 18 * mm, 18 * mm, 18 * mm], repeatRows=1)
    style = _table_style()
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("LINEABOVE", (0, -1), (-1, -1), 1, NAVY)
    style.add("BACKGROUND", (0, -1), (-1, -1), colors.white)
    st.setStyle(style)
    story.append(st)
    story.append(Paragraph(f"Showing 1 to {len(loan.repayment_schedules)} of {len(loan.repayment_schedules)} entries", small))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"For further clarifications please contact us on {s.helpline_number} or "
        f"{s.grievance_email}. Please quote your Loan Number when you contact us.",
        small,
    ))

    # --- verification QR ---
    # Scan to confirm this exact statement (loan no. + total dues + date)
    # was genuinely issued by this portal — see doc_verify.py for what's
    # signed in and why a QR rather than a lookup table.
    doc_date = datetime.now(IST).strftime("%d-%m-%Y")
    url = verify_url("statement", loan.agreement_no, total_dues, doc_date)
    qr_img = Image(BytesIO(qr_png(url)), width=20 * mm, height=20 * mm)
    qr_row = Table(
        [[qr_img, Paragraph(
            "Scan to verify this statement was genuinely issued by "
            f"{s.legal_name} — confirms Loan No., Total Dues, and issue date.",
            small,
        )]],
        colWidths=[24 * mm, 146 * mm],
    )
    qr_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 8))
    story.append(qr_row)

    doc.build(story)
    return buf.getvalue()


def _table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
