from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from .models import NotificationEvent


class NotificationInboxView(LoginRequiredMixin, ListView):
    model = NotificationEvent
    template_name = "notifications/inbox.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return (
            NotificationEvent.objects.filter(recipient=self.request.user)
            .select_related("recipient")
            .order_by("-created_at")
        )


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, event_id: int) -> HttpResponse:
        event = NotificationEvent.objects.filter(
            id=event_id,
            recipient=request.user,
        ).first()
        if event is None:
            raise Http404("Notification not found")

        event.mark_read()
        return redirect("notifications:inbox")


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest) -> HttpResponse:
        NotificationEvent.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())
        return redirect("notifications:inbox")
