from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import ListView

from .forms import WorkoutLogForm
from .models import WorkoutLog


class WorkoutLogListCreateView(LoginRequiredMixin, ListView):
    model = WorkoutLog
    template_name = "progress/logs.html"
    context_object_name = "logs"

    def get_queryset(self):
        return WorkoutLog.objects.filter(performed_by=self.request.user).select_related(
            "plan", "community"
        ).order_by("-completed_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["log_form"] = kwargs.get("log_form") or WorkoutLogForm(user=self.request.user)
        return context

    def post(self, request: HttpRequest) -> HttpResponse:
        form = WorkoutLogForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            log.performed_by = request.user
            if log.plan and log.plan.community_id and not log.community_id:
                log.community = log.plan.community
            log.save()
            messages.success(request, "Workout log saved.")
            return redirect("progress:logs")

        response = self.render_to_response(self.get_context_data(log_form=form))
        response.status_code = 400
        return response
