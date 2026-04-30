from django.urls import path
from .views import (
    EmailLogListView, COARecordListView, EscalationRecordListView, TriggerEmailProcessingView,
    dashboard, emails_page, coa_page, escalations_page, trigger_view
)

urlpatterns = [
    # API
    path("api/emails/",      EmailLogListView.as_view(),          name="email-list"),
    path("api/coa/",         COARecordListView.as_view(),          name="coa-list"),
    path("api/escalations/", EscalationRecordListView.as_view(),   name="escalation-list"),
    path("api/trigger/",     TriggerEmailProcessingView.as_view(), name="trigger-processing"),

    # UI
    path("dashboard/",              dashboard,         name="dashboard"),
    path("dashboard/emails/",       emails_page,       name="emails-page"),
    path("dashboard/coa/",          coa_page,          name="coa-page"),
    path("dashboard/escalations/",  escalations_page,  name="escalations-page"),
    path("dashboard/trigger/",      trigger_view,      name="trigger-view"),
]
