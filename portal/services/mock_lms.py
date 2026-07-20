"""Realistic AllCloud fixtures served when LMS_MOCK=true.

Lets the whole portal (login -> dashboard -> dues -> QR -> confirm ->
receipt) run end-to-end with zero LMS connectivity. Mock customer:
mobile 9876543210, DOB 1990-06-15, two live loans (2W + 3W), one overdue.
Agreement login: LNTSPAR-240300005 or LNTSPAR-230900112 + mobile 9876543210
+ DOB 1990-06-15.
"""

import datetime as dt

MOCK_MOBILE = "9876543210"

# 1x1 teal PNG so templates can render <img src="data:image/png;base64,...">
_QR_PLACEHOLDER = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkqPhf"
    "DwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _today(days: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


MOCK_CUSTOMER_ID = "CUST00042"
MOCK_DOB = "1990-06-15"

# Mirrors the real AllCloud shape: GetLoanAgreementNoAsync exposes identity
# only via lstCoBorrowers[].CustomerId (no DOB/contact at the loan level);
# GetCustomerSearch is the only source of DOB, keyed by mobile.
_CO_BORROWERS = [
    {"CustomerId": MOCK_CUSTOMER_ID, "OrderTypeId": "Primary", "BorrowerName": "RAMESH KUMAR"}
]

_SCHEDULE_2W = [
    {"InstallmentNo": 1, "DueAmount": 3450.0},
    {"InstallmentNo": 2, "DueAmount": 3450.0},
]
_SCHEDULE_3W = [
    {"InstallmentNo": 1, "DueAmount": 7825.0},
    {"InstallmentNo": 2, "DueAmount": 7825.0},
]

_LOANS = [
    {
        "FinanceId": "240300005",
        "AgreementNo": "LNTSPAR-240300005",
        "ProductType": "Two Wheeler Loan",
        "CustomerName": "RAMESH KUMAR",
        "LoanAmount": 85000.0,
        "EMIAmount": 3450.0,
        "NextDueDate": _today(6),
        "OverdueAmount": 0.0,
        "DPD": 0,
        "Status": "Active",
        "Duration": 30,
        "NoOfPaidEMI": 20.0,
        "EMIDueCount": 0.0,
        "LPIDues": 0.0,
        "TotalVASDues": 0.0,
        "TotalEMIOverdueAmount": 0.0,
        "lstCoBorrowers": _CO_BORROWERS,
        "RepaymentSchedules": _SCHEDULE_2W,
    },
    {
        "FinanceId": "230900112",
        "AgreementNo": "LNTSPAR-230900112",
        "ProductType": "Three Wheeler Loan",
        "CustomerName": "RAMESH KUMAR",
        "LoanAmount": 210000.0,
        "EMIAmount": 7825.0,
        "NextDueDate": _today(-12),
        "OverdueAmount": 7825.0,
        "DPD": 12,
        "Status": "Overdue",
        "Duration": 24,
        "NoOfPaidEMI": 14.0,
        "EMIDueCount": 1.0,
        "LPIDues": 235.0,
        "TotalVASDues": 150.0,
        "TotalEMIOverdueAmount": 8210.0,
        "lstCoBorrowers": _CO_BORROWERS,
        "RepaymentSchedules": _SCHEDULE_3W,
    },
]

_DUES = {
    "240300005": {
        "FinanceId": "240300005",
        "BalanceAmount": 3450.0,
        "LPIDue": 0.0,
        "CollectionCharges": 0.0,
        "VasDue": 0.0,
        "HandLoan": 0.0,
        "EMIAmount": 3450.0,
        "EmiDues": [{"EMIType": "Up Coming", "EMIAmount": 3450.0, "EMIDueDate": _today(6)}],
    },
    "230900112": {
        "FinanceId": "230900112",
        "BalanceAmount": 7825.0,
        "LPIDue": 235.0,       # penal charges @ contracted rate, 12 DPD
        "CollectionCharges": 150.0,
        "VasDue": 0.0,
        "HandLoan": 0.0,
        "EMIAmount": 7825.0,
        "EmiDues": [{"EMIType": "Over Due", "EMIAmount": 7825.0, "EMIDueDate": _today(-12)}],
    },
}


def customer_search(mobile: str):
    if mobile == MOCK_MOBILE:
        return [{
            "CustomerId": MOCK_CUSTOMER_ID, "CustomerName": "RAMESH KUMAR",
            "Contact": mobile, "DOB": MOCK_DOB,
        }]
    return []


def loans_by_mobile(mobile: str):
    return list(_LOANS) if mobile == MOCK_MOBILE else []


def loan_by_agreement(agreement_no: str):
    for loan in _LOANS:
        if loan["AgreementNo"].upper() == agreement_no.upper():
            return [dict(loan)]
    return []


def repayment_for_loan(finance_id: str):
    return dict(_DUES.get(str(finance_id), {"FinanceId": finance_id, "DueAmount": 0.0}))


_LCC = {
    "LNTSPAR-240300005": {
        "FinanceId": "240300005", "AgreementNo": "LNTSPAR-240300005",
        "CustomerName": "RAMESH KUMAR", "CustomerContact": MOCK_MOBILE,
        "InstallmentDueDate": _today(6), "CurrentMonthTBC": 3450.0,
        "TotalDues": 3450.0, "LPCDue": 0.0, "VasDueAmount": 0.0,
        "HandLoanDueAmount": 0.0, "EMIDueCount": 1.0, "RunningEmiCount": 10,
        "Status": "Active",
    },
    "LNTSPAR-230900112": {
        "FinanceId": "230900112", "AgreementNo": "LNTSPAR-230900112",
        "CustomerName": "RAMESH KUMAR", "CustomerContact": MOCK_MOBILE,
        "InstallmentDueDate": _today(-12), "CurrentMonthTBC": 7825.0,
        "TotalDues": 8210.0, "LPCDue": 235.0, "VasDueAmount": 0.0,
        "HandLoanDueAmount": 0.0, "EMIDueCount": 1.0, "RunningEmiCount": 5,
        "Status": "Active",  # confirmed live: Status text alone isn't a
                              # reliable overdue signal — LPCDue is
    },
}


def lcc_details(agreement_no: str):
    return dict(_LCC.get(agreement_no.upper(), {"AgreementNo": agreement_no}))


def qr_code(body: dict):
    # Mirrors the confirmed-live GetQRCode shape (2026-07-15): no QR image,
    # just a payment-gateway checkout URL + urn reference.
    urn = f"162-mock-{body.get('FinanceId')}"
    return {
        "Status": 1,
        "custname": "RAMESH KUMAR",
        "urn": urn,
        "dueamount": str(body.get("TotalAmount")),
        "URL": f"https://pay.alcd.in/Checkout/Pay?id={urn}&route=608",
        "aggrementno": "LNTSPAR-230900112",
    }
