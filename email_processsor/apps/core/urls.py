from django.urls import path
from .views import (
    EmailLogListView, EscalationRecordListView, TriggerEmailProcessingView,
    SkipLogListView, 
)

urlpatterns = [
    path("api/emails/",      EmailLogListView.as_view(),           name="email-list"),
    path("api/skiplogs/",    SkipLogListView.as_view(),            name="skiplog-list"),
    path("api/escalations/", EscalationRecordListView.as_view(),   name="escalation-list"),
    path("api/trigger/",     TriggerEmailProcessingView.as_view(), name="trigger-processing"),
    # path("api/escalations/<int:record_id>/resend/", resend_escalation, name="resend-escalation"),
]
