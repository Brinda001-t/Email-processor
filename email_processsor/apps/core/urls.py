from django.contrib.auth.views import LoginView
from django.urls import path
from .views import (
    EmailLogListView, EscalationRecordListView, TriggerEmailProcessingView,
    dashboard, emails_page, escalations_page, skip_log_page,
    trigger_view, resend_escalation, logout_view,
)

urlpatterns = [
    path("login/",  LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", logout_view,                                         name="logout"),

    # API
    path("api/emails/",      EmailLogListView.as_view(),          name="email-list"),
    path("api/escalations/", EscalationRecordListView.as_view(),  name="escalation-list"),
    path("api/trigger/",     TriggerEmailProcessingView.as_view(), name="trigger-processing"),

    # Escalation actions
    path("api/escalations/<int:record_id>/resend/", resend_escalation, name="resend-escalation"),

    # UI
    path("dashboard/",             dashboard,        name="dashboard"),
    path("dashboard/emails/",      emails_page,      name="emails-page"),
    path("dashboard/escalations/", escalations_page, name="escalations-page"),
    path("dashboard/skip-log/",    skip_log_page,    name="skip-log-page"),
    path("dashboard/trigger/",     trigger_view,     name="trigger-view"),
]
