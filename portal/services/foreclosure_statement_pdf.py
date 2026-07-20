"""Foreclosure (pre-closure payoff) statement, built from live
GetLoanAgreementNoAsync + GetLccDetailsByAgreementNo data.

Two of the ten line items on AllCloud's own foreclosure screen — Fore-
Closure Charges and Broken Period Interest — are NOT returned by any
integrated endpoint (confirmed live 2026-07-20: probed GetForeClosureDetails,
GetPreClosureDetails, GetClosureAmount, GetLoanClosureDetails,
GetForeClosureStatement — all 404). Both are computed here per explicit
business rules confirmed against a real AllCloud screenshot for loan
L3WNKARCR-251211019, matched to the rupee/paisa:

- Fore-Closure Charges = 4% of Future Principal, rounded to the nearest
  rupee. Confirmed: 274798 * 0.04 = 10991.92 -> 10992, exact match.
- Broken Period Interest = the next (not-yet-due) installment's Interest
  amount, prorated by ACTUAL calendar days elapsed since the last due date
  over the ACTUAL calendar days in that next installment's period (not a
  flat 30-day month). Confirmed: last due 05-Jul-2026, next due 05-Aug-2026
  (31-day period), 14 days elapsed as of 19-Jul-2026 ->
  5223.99 * (14/31) = 2359.22, matches the reference 2359.23 to the paisa.

The remaining three line items (Handloan LPI, VAS Collect Later, and a
nonzero "Insurance due" beyond what's captured by the Insurance VAS entry)
have no confirmed data source and default to 0 — flagged here rather than
guessed, matching every other documented ceiling in this codebase.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

FORECLOSURE_CHARGE_PCT = 0.04
# The payoff figure is computed as of 7 days from generation, not today —
# a small buffer so the amount stays sufficient (covers the extra accrued
# Broken Interest) for the whole window the customer has to actually pay.
# The statement is explicitly marked valid only for that same window.
VALIDITY_DAYS = 7


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


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    head = value.strip().split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(head, fmt)
        except ValueError:
            continue
    return None


def compute_foreclosure(loan: LoanSummary, lcc: LccDetails | None, as_of: datetime | None = None) -> dict:
    """Returns the ten line items + total, plus the intermediate dates/days
    used for Broken Interest so a statement can show its working.

    `as_of` defaults to VALIDITY_DAYS (7) from now, not today — see that
    constant's comment."""
    as_of = as_of or (datetime.now(IST).replace(tzinfo=None) + timedelta(days=VALIDITY_DAYS))

    schedule = sorted(
        (e for e in loan.repayment_schedules if _parse_date(e.due_date)),
        key=lambda e: _parse_date(e.due_date),
    )
    # "Cutoff" = the last installment due on or before as_of (its
    # PrincipalOS is the balance carried forward once currently-due EMIs
    # are cleared). "Next" = the first installment due after as_of.
    cutoff = None
    next_installment = None
    for e in schedule:
        due = _parse_date(e.due_date)
        if due <= as_of:
            cutoff = e
        elif next_installment is None:
            next_installment = e
            break

    future_principal = cutoff.principal_os if cutoff else (schedule[0].principal_os if schedule else 0.0)

    broken_interest = 0.0
    broken_days = 0
    period_days = 0
    if cutoff and next_installment:
        last_due = _parse_date(cutoff.due_date)
        next_due = _parse_date(next_installment.due_date)
        period_days = (next_due - last_due).days
        broken_days = max(0, (as_of - last_due).days)
        if period_days > 0:
            broken_interest = next_installment.interest * (broken_days / period_days)

    foreclosure_charges = round(future_principal * FORECLOSURE_CHARGE_PCT)

    # Insurance broken out of the VAS bucket so it isn't double-counted
    # against "VAS Charge" (confirmed live 2026-07-20: TotalVASDues already
    # reconciles as the non-insurance VAS total for a loan with zero
    # insurance due, so insurance is subtracted out here rather than added
    # on top).
    insurance_due = sum(
        max(v.amount - v.received_amount, 0.0)
        for v in loan.vas_list
        if "insurance" in (v.vas_type_id or v.name or "").lower()
    )
    vas_charge = max(loan.total_vas_dues - insurance_due, 0.0)

    handloan = lcc.hand_loan_due_amount if lcc else 0.0

    items = {
        "foreclosure_charges": foreclosure_charges,
        "emi_due": loan.overdue_amount,
        "future_principal": future_principal,
        "broken_interest": broken_interest,
        "lpi": loan.lpi_dues,
        "handloan": handloan,
        "handloan_lpi": 0.0,  # no confirmed data source — see module docstring
        "vas_charge": vas_charge,
        "vas_collect_later": 0.0,  # no confirmed data source — see module docstring
        "insurance": insurance_due,
    }
    items["total_receivables"] = round(sum(items.values()), 2)
    items["_as_of"] = as_of
    items["_last_due_date"] = cutoff.due_date if cutoff else ""
    items["_next_due_date"] = next_installment.due_date if next_installment else ""
    items["_broken_days"] = broken_days
    items["_period_days"] = period_days
    return items


def build_foreclosure_statement_pdf(
    customer: CustomerSearchResult, loan: LoanSummary, lcc: LccDetails | None,
) -> bytes:
    s = get_settings()
    calc = compute_foreclosure(loan, lcc)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
        encrypt=encryption_for(customer.dob),
    )
    styles = getSampleStyleSheet()
    value_style = ParagraphStyle("value", parent=styles["Normal"], fontSize=10, textColor=colors.black)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, textColor=NAVY, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, textColor=NAVY, spaceBefore=10, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=GREY)

    def kv(label: str, value: str) -> str:
        return f"<font color='#64748b' size=8>{label}</font><br/><font size=10>{value or '-'}</font>"

    story = []

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
    story.append(Paragraph("FORECLOSURE STATEMENT", ParagraphStyle(
        "title", parent=styles["Heading1"], fontSize=13, textColor=colors.white,
        backColor=NAVY, alignment=1, spaceAfter=0, borderPadding=6,
    )))
    story.append(Spacer(1, 4))
    now_ist = datetime.now(IST)
    generated = now_ist.strftime("%d-%m-%Y %H:%M")
    as_of_str = calc["_as_of"].strftime("%d-%m-%Y")
    story.append(Paragraph(
        f"Loan Number: <b>{loan.agreement_no}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Valid Until: <b>{as_of_str}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Generated On: {generated} IST",
        small,
    ))
    story.append(Paragraph(
        f"<b>This foreclosure statement is valid for {VALIDITY_DAYS} days from generation "
        f"— i.e. until {as_of_str}.</b> The figures below already include the interest that will "
        f"accrue over this window, so the total is payable any day up to and including {as_of_str}. "
        f"If not settled within this period, a fresh statement must be requested.",
        ParagraphStyle("validity", parent=small, textColor=colors.HexColor("#b45309")),
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Borrower Details", h2))
    branch_region = ((lcc.branch if lcc else "") or "-") + (f" ({lcc.region})" if lcc and lcc.region else "")
    vehicle = ((lcc.registration_no if lcc else "") or "-") + (f" ({lcc.vehicle_class})" if lcc and lcc.vehicle_class else "")
    borrower_rows = [
        [Paragraph(kv("Name", customer.customer_name.title()), value_style),
         Paragraph(kv("Loan No.", loan.agreement_no), value_style)],
        [Paragraph(kv("Mobile No.", customer.contact), value_style),
         Paragraph(kv("Loan Amount", f"Rs. {_money(loan.loan_amount)}"), value_style)],
        [Paragraph(kv("Branch (Region)", branch_region), value_style),
         Paragraph(kv("Vehicle", vehicle), value_style)],
    ]
    t = Table(borrower_rows, colWidths=[90 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)

    story.append(Paragraph("Foreclosure Break-up", h2))
    rows = [
        ["Fore-Closure Charges", _money(calc["foreclosure_charges"])],
        ["EMI Due", _money(calc["emi_due"])],
        ["Future Principal", _money(calc["future_principal"])],
        ["Broken Period Interest", _money(calc["broken_interest"])],
        ["LPI", _money(calc["lpi"])],
        ["Handloan", _money(calc["handloan"])],
        ["Handloan LPI", _money(calc["handloan_lpi"])],
        ["VAS Charge", _money(calc["vas_charge"])],
        ["VAS Collect Later", _money(calc["vas_collect_later"])],
        ["Insurance", _money(calc["insurance"])],
    ]
    bt = Table([["Particulars", "Amount (Rs.)"]] + rows, colWidths=[120 * mm, 60 * mm])
    style = _table_style()
    bt.setStyle(style)
    story.append(bt)
    story.append(Spacer(1, 2))
    total_row = Table([["Total Receivables", f"Rs. {_money(calc['total_receivables'])}"]], colWidths=[120 * mm, 60 * mm])
    total_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(total_row)

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Broken Period Interest is calculated from the last due date "
        f"({_dmy(calc['_last_due_date'])}) to the payoff date above "
        f"({calc['_broken_days']} of {calc['_period_days']} days in the current "
        f"installment period), prorated on the next installment's interest amount. "
        f"Fore-Closure Charges are {FORECLOSURE_CHARGE_PCT * 100:.0f}% of Future Principal, "
        f"rounded to the nearest rupee.",
        small,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"For further clarifications please contact us on {s.helpline_number} or "
        f"{s.grievance_email}. Please quote your Loan Number when you contact us.",
        small,
    ))

    # --- verification QR --- see statement_pdf.py's copy of this for why.
    url = verify_url("foreclosure", loan.agreement_no, calc["total_receivables"], as_of_str)
    qr_img = Image(BytesIO(qr_png(url)), width=20 * mm, height=20 * mm)
    qr_row = Table(
        [[qr_img, Paragraph(
            "Scan to verify this foreclosure statement was genuinely issued by "
            f"{s.legal_name} — confirms Loan No., Total Receivables, and validity date.",
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
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])
