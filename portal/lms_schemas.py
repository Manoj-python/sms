"""Pydantic models for AllCloud responses.

Schemas are undocumented, so every model tolerates unknown fields
(extra="ignore") and uses alias fallbacks via validation_alias where field
naming is uncertain. Use /dev/lms-probe in UAT to inspect raw payloads and
tighten these over time.

Confirmed live (2026-07-14): AllCloud sends CustomerId/ContactNumber as JSON
numbers, not strings, on GetCustomerSearch — coerce_numbers_to_str handles
that (and any other str-typed field AllCloud sends numerically) app-wide.
"""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class TolerantModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", populate_by_name=True, coerce_numbers_to_str=True
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data):
        # Confirmed live (2026-07-17): AllCloud sends explicit JSON null for
        # string fields once a loan is past scheduled events — e.g.
        # GetLccDetailsByAgreementNo's InstallmentDueDate is null for a loan
        # past its full EMI tenure but still carrying dues. Pydantic rejects
        # None for a non-Optional str field, which without this silently
        # crashed the whole model and made callers fall back to a much less
        # reliable data source. Dropping null keys lets the field's own
        # default apply instead.
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None}
        return data


class CustomerSearchResult(TolerantModel):
    customer_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CustomerId", "CustomerID", "customerId", "Id"),
    )
    # Confirmed live (2026-07-16): GetCustomerSearch has NO "CustomerName"
    # field — only FirstName/LastName separately.
    first_name: str = Field(default="", validation_alias=AliasChoices("FirstName",))
    last_name: str = Field(default="", validation_alias=AliasChoices("LastName",))
    customer_name_raw: str = Field(
        default="",
        validation_alias=AliasChoices("CustomerName", "Name", "customerName"),
    )
    contact: str = Field(
        default="", validation_alias=AliasChoices("Contact", "ContactNumber", "Mobile")
    )
    # Confirmed live (2026-07-14): GetCustomerSearch returns DOB — the
    # agreement-lookup endpoint does NOT, so this is the only source of DOB
    # for the alternate login flow.
    dob: str = Field(default="", validation_alias=AliasChoices("DOB", "DateOfBirth"))
    # Confirmed live (2026-07-18): customer profile fields for the portal's
    # "View profile" page — PhotoURL is a presigned S3 URL (~10 min expiry),
    # never persisted anywhere, only ever rendered fresh from a live call.
    father_name: str = Field(default="", validation_alias=AliasChoices("FatherName",))
    email: str = Field(default="", validation_alias=AliasChoices("Email",))
    photo_url: str = Field(default="", validation_alias=AliasChoices("PhotoURL",))
    masked_aadhaar: str = Field(default="", validation_alias=AliasChoices("MaskedAadarCard",))
    address_line1: str = Field(default="", validation_alias=AliasChoices("PrimaryAddressLine1",))
    address_line2: str = Field(default="", validation_alias=AliasChoices("PrimaryAddressLine2",))
    address_area: str = Field(default="", validation_alias=AliasChoices("PrimaryArea",))
    address_town: str = Field(default="", validation_alias=AliasChoices("PrimaryTown",))
    address_taluka: str = Field(default="", validation_alias=AliasChoices("PrimaryTaluka",))
    address_postcode: str = Field(default="", validation_alias=AliasChoices("PrimaryPostcode",))
    address_landmark: str = Field(default="", validation_alias=AliasChoices("PrimaryLandmark",))

    @property
    def customer_name(self) -> str:
        return self.customer_name_raw or f"{self.first_name} {self.last_name}".strip()

    @property
    def full_address(self) -> str:
        parts = [
            self.address_line1, self.address_line2, self.address_area,
            self.address_town, self.address_taluka, self.address_postcode,
            self.address_landmark,
        ]
        return ", ".join(p.strip() for p in parts if p and p.strip())


class CoBorrower(TolerantModel):
    customer_id: str = Field(
        default="", validation_alias=AliasChoices("CustomerId", "CustomerID")
    )
    order_type_id: str = Field(
        default="", validation_alias=AliasChoices("OrderTypeId", "OrderType")
    )
    entity_type_id: str = Field(default="", validation_alias=AliasChoices("EntityTypeId",))
    borrower_name: str = Field(default="", validation_alias=AliasChoices("BorrowerName",))


class RepaymentScheduleEntry(TolerantModel):
    """Confirmed live (2026-07-18): GetLoanAgreementNoAsync's RepaymentSchedules
    is a full per-installment ledger — due date/amount, principal/interest
    split, running principal outstanding, and what was actually paid (amount/
    date/mode) plus penal charges (LPC) charged and received. This is the
    statement-of-account "transaction history" data; there's no separate
    flat debit/credit journal endpoint confirmed."""

    installment_no: int = Field(default=0, validation_alias=AliasChoices("InstallmentNo",))
    due_date: str = Field(default="", validation_alias=AliasChoices("DueDate",))
    due_amount: float = Field(default=0.0, validation_alias=AliasChoices("DueAmount",))
    principal: float = Field(default=0.0, validation_alias=AliasChoices("Principal",))
    interest: float = Field(default=0.0, validation_alias=AliasChoices("Interest",))
    principal_os: float = Field(default=0.0, validation_alias=AliasChoices("PrincipalOS",))
    # Confirmed live: PaidAmount/PaymentDate/PaymentMode arrive as "" (empty
    # string, not absent/null) for not-yet-due installments.
    paid_amount: str = Field(default="", validation_alias=AliasChoices("PaidAmount",))
    payment_date: str = Field(default="", validation_alias=AliasChoices("PaymentDate",))
    payment_mode: str = Field(default="", validation_alias=AliasChoices("PaymentMode",))
    pending_amount: float = Field(default=0.0, validation_alias=AliasChoices("PendingAmount",))
    payment_status: str = Field(default="", validation_alias=AliasChoices("PaymentStatus",))
    lpc: float = Field(default=0.0, validation_alias=AliasChoices("LPC",))
    lpc_received: float = Field(default=0.0, validation_alias=AliasChoices("LPCReceived",))
    collection_charges: float = Field(default=0.0, validation_alias=AliasChoices("CollectionCharges",))


class VasEntry(TolerantModel):
    """One row of GetLoanAgreementNoAsync's VASs — non-EMI charges/credits
    (security deposit, processing fees, insurance, ...) confirmed live
    2026-07-18. Used on the statement to show the disbursement-time
    deductions (e.g. security deposit) that explain Loan Amount vs
    Disbursed Amount."""

    name: str = Field(default="", validation_alias=AliasChoices("Name",))
    amount: float = Field(default=0.0, validation_alias=AliasChoices("Amount",))
    vas_type_id: str = Field(default="", validation_alias=AliasChoices("VASTypeId",))
    received_amount: float = Field(default=0.0, validation_alias=AliasChoices("ReceivedAmount",))
    received_date: str = Field(default="", validation_alias=AliasChoices("ReceivedDate",))
    # Confirmed live 2026-07-18: for recurring charges (e.g. UPI NACH Bounce
    # Charges) that get settled in a later lump-sum batch, AllCloud's own
    # receipt listing dates each occurrence by DueDate — ReceivedDate only
    # reflects when the batch was actually cleared, which can be months
    # later and collapses several distinct charges onto one date.
    due_date: str = Field(default="", validation_alias=AliasChoices("DueDate",))
    vas_due: float = Field(default=0.0, validation_alias=AliasChoices("VASDue",))


class LoanSummary(TolerantModel):
    finance_id: str = Field(
        default="",
        validation_alias=AliasChoices("FinanceId", "FinanceID", "financeId", "LoanId"),
    )
    agreement_no: str = Field(
        default="",
        validation_alias=AliasChoices("AgreementNo", "AgreementNumber", "agreementNo"),
    )
    # Confirmed live (2026-07-14) field names from GetLoanAgreementNoAsync —
    # GetLoanByMobileNumber returns blank/zero for all of these under the
    # originally-guessed names (ProductType/OverdueAmount/DPD/Status), so the
    # real AllCloud names are added alongside the guesses.
    product_type: str = Field(
        default="",
        validation_alias=AliasChoices(
            "ProductType", "Product", "ProductName", "Scheme", "LoanType", "ProductCategory"
        ),
    )
    customer_name: str = Field(
        default="", validation_alias=AliasChoices("CustomerName", "Name")
    )
    emi_amount: float = Field(
        default=0.0,
        validation_alias=AliasChoices("EMIAmount", "EmiAmount", "EMI", "InstallmentAmount"),
    )
    # Confirmed live (2026-07-15): GetLoanAgreementNoAsync has BOTH
    # NextPaymentDate (stale/last-processed — NOT the next due date) and
    # NextEMIDueDate (the real next due date). NextEMIDueDate must win, so
    # it's listed first — AliasChoices picks the first alias present.
    next_due_date: str = Field(
        default="",
        validation_alias=AliasChoices(
            "NextEMIDueDate", "NextDueDate", "DueDate", "NextInstallmentDate", "NextPaymentDate"
        ),
    )
    # Confirmed live (2026-07-15): the payload has SEVERAL "total" fields at
    # once (TotalDueAmount=26403, TotalEMIOverdueAmount=28461,
    # TotalLoanOverdueAmount=98047, LoanTotalDue=95989) — the last two are
    # full-payoff figures, not current dues. TotalDueAmount is the correct
    # "EMI overdue" amount and must be listed first.
    overdue_amount: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "TotalDueAmount", "OverdueAmount", "TotalOverdue", "OverDueAmount",
            "TotalLoanOverdueAmount", "TotalEMIOverdueAmount", "LoanTotalDue",
        ),
    )
    dpd: int = Field(
        default=0, validation_alias=AliasChoices("DPD", "Dpd", "DaysPastDue", "DPDDays")
    )
    status: str = Field(
        default="",
        validation_alias=AliasChoices(
            "Status", "LoanStatus", "AccountStatus", "StatusId", "DisbursementStatus"
        ),
    )
    loan_amount: float = Field(
        default=0.0,
        validation_alias=AliasChoices("LoanAmount", "FinanceAmount", "SanctionAmount", "TotalAmount"),
    )
    # Confirmed live (2026-07-14), GetLoanAgreementNoAsync loan-detail page
    # fields (see routers/payments.py pay_page):
    duration: int = Field(default=0, validation_alias=AliasChoices("Duration",))
    no_of_paid_emi: float = Field(default=0.0, validation_alias=AliasChoices("NoOfPaidEMI",))
    emi_due_count: float = Field(default=0.0, validation_alias=AliasChoices("EMIDueCount",))
    lpi_dues: float = Field(default=0.0, validation_alias=AliasChoices("LPIDues",))
    total_vas_dues: float = Field(default=0.0, validation_alias=AliasChoices("TotalVASDues",))
    total_emi_overdue_amount: float = Field(
        default=0.0, validation_alias=AliasChoices("TotalEMIOverdueAmount",)
    )
    repayment_schedules: list[RepaymentScheduleEntry] = Field(
        default_factory=list, validation_alias=AliasChoices("RepaymentSchedules",)
    )
    # Confirmed live (2026-07-14): GetLoanAgreementNoAsync has NEITHER a
    # DOB NOR a Contact/mobile field at the loan level — the only identity
    # data is the primary borrower's CustomerId under lstCoBorrowers, which
    # is cross-checked against GetCustomerSearch's CustomerId instead.
    co_borrowers: list[CoBorrower] = Field(
        default_factory=list, validation_alias=AliasChoices("lstCoBorrowers", "CoBorrowers")
    )
    # --- Statement-of-account fields — confirmed live 2026-07-18 -----------
    vas_list: list[VasEntry] = Field(default_factory=list, validation_alias=AliasChoices("VASs",))
    start_date: str = Field(default="", validation_alias=AliasChoices("StartDate",))
    emi_start_date: str = Field(default="", validation_alias=AliasChoices("EMIStartDate",))
    emi_end_date: str = Field(default="", validation_alias=AliasChoices("EMIEndDate",))
    installment_type_id: str = Field(default="", validation_alias=AliasChoices("InstallmentTypeId",))
    mode_of_repayment_id: str = Field(default="", validation_alias=AliasChoices("ModeOfRePaymentId",))
    utr_no: str = Field(default="", validation_alias=AliasChoices("UTRNo",))
    # DisbursementStatus ("Disbursed") and StatusId ("Open") are distinct —
    # kept apart from the ambiguous `status` field above (which already
    # falls back to StatusId/DisbursementStatus when nothing more specific
    # is present, so is unreliable for telling the two apart).
    disbursement_status: str = Field(default="", validation_alias=AliasChoices("DisbursementStatus",))
    status_id: str = Field(default="", validation_alias=AliasChoices("StatusId",))
    # ROI(%) | APR(%) on the statement = YearlyIndicativeROI | EffectiveAPRPercente
    # (confirmed live against a real statement PDF, 2026-07-18).
    yearly_indicative_roi: float = Field(default=0.0, validation_alias=AliasChoices("YearlyIndicativeROI",))
    effective_apr: float = Field(default=0.0, validation_alias=AliasChoices("EffectiveAPRPercente",))
    lpc_interest: float = Field(default=0.0, validation_alias=AliasChoices("LPCInterest",))
    total_principal_due: float = Field(default=0.0, validation_alias=AliasChoices("TotalPrincipalDue",))
    total_interest_due: float = Field(default=0.0, validation_alias=AliasChoices("TotalInterestDue",))

    @property
    def primary_customer_id(self) -> str | None:
        for cb in self.co_borrowers:
            if cb.order_type_id.lower() == "primary" and cb.customer_id:
                return cb.customer_id
        return self.co_borrowers[0].customer_id if self.co_borrowers else None

    @property
    def primary_customer_name(self) -> str:
        for cb in self.co_borrowers:
            if cb.order_type_id.lower() == "primary" and "customer" in cb.entity_type_id.lower():
                return cb.borrower_name
        return self.customer_name

    @property
    def guarantors(self) -> list["CoBorrower"]:
        return [cb for cb in self.co_borrowers if "guarantor" in cb.entity_type_id.lower()]

    @property
    def disbursed_amount(self) -> float:
        """Loan Amount minus security-deposit-style VAS deductions taken at
        disbursement — confirmed live 2026-07-18 against a real statement
        (Loan Amount 63,000 - Security Deposit 5,000 = Disbursed 58,000)."""
        deductions = sum(
            v.amount for v in self.vas_list
            if "securitydeposit" in v.vas_type_id.lower().replace(" ", "")
        )
        return round(self.loan_amount - deductions, 2)

    @property
    def last_paid_date(self) -> str:
        for entry in reversed(self.repayment_schedules):
            if entry.payment_date:
                # Confirmed live (2026-07-18): PaymentDate can itself be a
                # comma-separated list when an installment received
                # multiple partial payments (e.g. "17-12-2025, 12-01-2026")
                # — the most recent one is the actual last-paid date.
                parts = [p.strip() for p in entry.payment_date.split(",") if p.strip()]
                return parts[-1] if parts else ""
        return ""

    @property
    def regular_emi_amount(self) -> float:
        """The steady-state EMI, taken from the 2nd schedule entry — the
        1st installment's DueAmount often differs (day-1 adjustments)."""
        if len(self.repayment_schedules) > 1:
            return self.repayment_schedules[1].due_amount
        if self.repayment_schedules:
            return self.repayment_schedules[0].due_amount
        return self.emi_amount


class EmiDueEntry(TolerantModel):
    """One row of GetRepaymentForLoanByLoanId's confirmed-live `EmiDues`
    breakdown — EMIType is "Over Due" or "Up Coming"."""

    emi_type: str = Field(default="", validation_alias=AliasChoices("EMIType",))
    emi_amount: float = Field(default=0.0, validation_alias=AliasChoices("EMIAmount",))
    due_date: str = Field(default="", validation_alias=AliasChoices("EMIDueDate",))


class RepaymentDue(TolerantModel):
    """Live dues — always fetched fresh from LMS, never cached.

    Confirmed live (2026-07-14) field names differ substantially from the
    originally-guessed ones: the current-due amount is `BalanceAmount` /
    `EMIdues` (not `DueAmount`), penal charges are `LPIDue` (not
    `LPIAmount`), and there is no flat overdue-amount/next-due-date field at
    all — both live only inside the nested `EmiDues` breakdown, keyed by
    `EMIType` ("Over Due" / "Up Coming"). GetLoanByMobileNumber's own
    overdue/status/next-due fields are unreliable, so the dashboard derives
    all of that from this endpoint instead — see `overdue_amount`/
    `next_due_date`/`is_overdue` below.
    """

    finance_id: str = Field(
        default="", validation_alias=AliasChoices("FinanceId", "FinanceID", "LoanId")
    )
    due_amount: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "DueAmount", "EMIDue", "InstallmentDue", "TotalDue", "BalanceAmount", "EMIdues"
        ),
    )
    lpi_amount: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "LPIAmount", "LPI", "LPC", "PenalCharges", "LatePaymentCharges", "LPIDue"
        ),
    )
    collection_charges: float = Field(
        default=0.0,
        validation_alias=AliasChoices("CollectionCharges", "CollectionCharge", "OtherCharges"),
    )
    vas_due: float = Field(default=0.0, validation_alias=AliasChoices("VasDue", "VASDue"))
    hand_loan: float = Field(default=0.0, validation_alias=AliasChoices("HandLoan",))
    total_due: float = Field(
        default=0.0,
        validation_alias=AliasChoices("TotalDueAmount", "TotalPayable", "TotalOutstandingDue"),
    )
    emi_amount: float = Field(
        default=0.0, validation_alias=AliasChoices("EMIAmount", "EmiAmount", "EMI")
    )
    emi_dues_breakdown: list[EmiDueEntry] = Field(
        default_factory=list, validation_alias=AliasChoices("EmiDues",)
    )

    def computed_total(self) -> float:
        return round(
            self.total_due
            or (self.due_amount + self.lpi_amount + self.collection_charges
                + self.vas_due + self.hand_loan),
            2,
        )

    @property
    def overdue_amount(self) -> float:
        return sum(
            e.emi_amount for e in self.emi_dues_breakdown if "over" in e.emi_type.lower()
        )

    @property
    def is_overdue(self) -> bool:
        return self.overdue_amount > 0

    @property
    def next_due_date(self) -> str:
        for e in self.emi_dues_breakdown:
            if "over" not in e.emi_type.lower() and e.due_date:
                return e.due_date
        return ""


class LccDetails(TolerantModel):
    """GetLccDetailsByAgreementNo (voicecall) — confirmed live 2026-07-14.
    A richer per-agreement summary than GetLoanByMobileNumber/
    GetRepaymentForLoanByLoanId: clean Status text, a real next-due date
    (InstallmentDueDate), and TotalDues/LPCDue already computed. Used to
    power the dashboard cards; the pay page still uses RepaymentDue for the
    granular due/LPI/collection-charge breakdown (RBI disclosure)."""

    finance_id: str = Field(default="", validation_alias=AliasChoices("FinanceId",))
    agreement_no: str = Field(default="", validation_alias=AliasChoices("AgreementNo",))
    region: str = Field(default="", validation_alias=AliasChoices("Region",))
    branch: str = Field(default="", validation_alias=AliasChoices("Branch",))
    customer_name: str = Field(default="", validation_alias=AliasChoices("CustomerName",))
    customer_contact: str = Field(default="", validation_alias=AliasChoices("CustomerContact",))
    vehicle_class: str = Field(default="", validation_alias=AliasChoices("VehicleClass",))
    registration_no: str = Field(default="", validation_alias=AliasChoices("RegistrationNo",))
    installment_due_date: str = Field(
        default="", validation_alias=AliasChoices("InstallmentDueDate",)
    )
    current_month_tbc: float = Field(
        default=0.0, validation_alias=AliasChoices("CurrentMonthTBC",)
    )
    total_dues: float = Field(default=0.0, validation_alias=AliasChoices("TotalDues",))
    lpc_due: float = Field(default=0.0, validation_alias=AliasChoices("LPCDue",))
    vas_due_amount: float = Field(default=0.0, validation_alias=AliasChoices("VasDueAmount",))
    hand_loan_due_amount: float = Field(
        default=0.0, validation_alias=AliasChoices("HandLoanDueAmount",)
    )
    emi_due_count: float = Field(default=0.0, validation_alias=AliasChoices("EMIDueCount",))
    running_emi_count: int = Field(default=0, validation_alias=AliasChoices("RunningEmiCount",))
    status: str = Field(default="", validation_alias=AliasChoices("Status",))
    # Non-empty once the vehicle has been repossessed as part of recovery.
    seize_date: str = Field(default="", validation_alias=AliasChoices("SeizeDate",))

    @property
    def is_seized(self) -> bool:
        return bool(self.seize_date)

    @property
    def is_overdue(self) -> bool:
        # Status ("Active"/"Closed"/...) doesn't reliably signal delinquency
        # — confirmed live, a loan with real arrears still showed "Active".
        # A nonzero late-payment charge is a much more direct overdue signal.
        return self.lpc_due > 0


class QRCodeResponse(TolerantModel):
    """GetQRCode — confirmed live 2026-07-15. Despite the name, the response
    carries NO QR image; it returns a payment-gateway checkout URL
    ({"Status":1, "custname", "urn", "dueamount", "URL":"https://pay.alcd.in/
    Checkout/Pay?id=...", "aggrementno"}). The portal renders a QR locally
    from that URL (scan option) alongside a Pay Now button (click option)."""

    qr_base64: str = Field(
        default="",
        validation_alias=AliasChoices(
            "QRCodeImage", "QRCode", "QRImage", "QrCodeBase64", "Base64Image", "QRString"
        ),
    )
    pay_url: str = Field(
        default="",
        validation_alias=AliasChoices("URL", "PaymentURL", "PayURL", "CheckoutURL"),
    )
    status: int = Field(default=0, validation_alias=AliasChoices("Status",))
    customer_name: str = Field(default="", validation_alias=AliasChoices("custname",))
    sms_link: str = Field(
        default="",
        validation_alias=AliasChoices("SMSLink", "PaymentLink", "SmsLink", "Link"),
    )
    reference: str = Field(
        default="",
        validation_alias=AliasChoices("urn", "ReferenceNo", "TransactionRef", "OrderId", "TxnId"),
    )
