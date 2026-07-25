from django.urls import path

from .views import (
    NotificationInboxView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationInboxView.as_view(), name="inbox"),
    path("mark-all-read/", NotificationMarkAllReadView.as_view(), name="mark_all_read"),
    path("<int:event_id>/mark-read/", NotificationMarkReadView.as_view(), name="mark_read"),
]
