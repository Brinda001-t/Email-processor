from django.urls import path
from .views import (
    EmailLogListView, COARecordListView, EscalationRecordListView, TriggerEmailProcessingView,
    dashboard, emails_page, coa_page, escalations_page, orders_page, skip_log_page,
    trigger_view, download_coa_pdf,
    resend_escalation,
)

urlpatterns = [
    # API
    path("api/emails/",      EmailLogListView.as_view(),          name="email-list"),
    path("api/coa/",         COARecordListView.as_view(),          name="coa-list"),
    path("api/escalations/", EscalationRecordListView.as_view(),   name="escalation-list"),
    path("api/trigger/",     TriggerEmailProcessingView.as_view(), name="trigger-processing"),

    # Escalation actions
    path("api/escalations/<int:record_id>/resend/", resend_escalation, name="resend-escalation"),

    # UI
    path("dashboard/",                              dashboard,         name="dashboard"),
    path("dashboard/emails/",                       emails_page,       name="emails-page"),
    path("dashboard/coa/",                          coa_page,          name="coa-page"),
    path("dashboard/escalations/",                  escalations_page,  name="escalations-page"),
    path("dashboard/orders/",                       orders_page,       name="orders-page"),
    path("dashboard/skip-log/",                      skip_log_page,     name="skip-log-page"),
    path("dashboard/trigger/",                      trigger_view,      name="trigger-view"),
    path("dashboard/coa/<int:record_id>/download/", download_coa_pdf,  name="download-coa-pdf"),
]
