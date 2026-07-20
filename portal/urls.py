from django.urls import path

from portal.views import auth, dashboard, dev, geo, payments, staff, verify

urlpatterns = [
    path("", dashboard.index, name="index"),
    path("verify/<str:token>", verify.verify_document, name="verify_document"),
    path("device-location", geo.device_location, name="device_location"),
    path("login", auth.login_page, name="login"),
    path("login/send-otp", auth.send_otp, name="send_otp"),
    path("login/resend-otp", auth.resend_otp, name="resend_otp"),
    path("login/verify-otp", auth.verify_otp, name="verify_otp"),
    path("login/agreement", auth.agreement_dispatch, name="agreement_login"),
    path("logout", auth.logout, name="logout"),
    path("lang/<str:code>", auth.set_lang, name="set_lang"),
    path("dashboard", dashboard.dashboard, name="dashboard"),
    path("profile", dashboard.profile_page, name="profile"),
    path("loan/<str:finance_id>", dashboard.loan_detail, name="loan_detail"),
    path("loan/<str:finance_id>/pay", payments.pay_page, name="pay_page"),
    path("loan/<str:finance_id>/downloads", payments.downloads_page, name="downloads_page"),
    path("loan/<str:finance_id>/statement.pdf", payments.statement_pdf, name="statement_pdf"),
    path("loan/<str:finance_id>/foreclosure.pdf", payments.foreclosure_statement_pdf, name="foreclosure_statement_pdf"),
    path("loan/<str:finance_id>/pay/qr", payments.generate_qr, name="generate_qr"),
    path("payment/<int:txn_id>/receipt.pdf", payments.receipt_pdf, name="receipt_pdf"),
    path("loan/<str:finance_id>/receipt/<str:target_date>.pdf",
         payments.receipt_by_date_pdf, name="receipt_by_date_pdf"),
    path("loan/<str:finance_id>/charges/<str:target_date>/receipt.pdf",
         payments.charge_receipt_pdf, name="charge_receipt_pdf"),
    path("dev/lms-probe", dev.lms_probe, name="lms_probe"),
    path("staff/login", staff.login_dispatch, name="staff_login"),
    path("staff/logout", staff.logout, name="staff_logout"),
    path("staff/report", staff.report, name="staff_report"),
]
