from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import ListView

from apps.communities.models import Community
from apps.workouts.models import WorkoutPlan

from .forms import WorkoutLogForm
from .models import WorkoutLog


class WorkoutLogListCreateView(LoginRequiredMixin, ListView):
    model = WorkoutLog
    template_name = "progress/logs.html"
    context_object_name = "logs"

    WINDOW_DAYS_OPTIONS = [7, 14, 30, 90]
    TREND_DAYS_OPTIONS = [7, 14, 30]

    def get_queryset(self):
        queryset = WorkoutLog.objects.filter(performed_by=self.request.user).select_related(
            "plan", "community"
        )

        window_days = self._window_days_filter()
        if window_days is not None:
            queryset = queryset.filter(
                completed_at__gte=timezone.now() - timedelta(days=window_days)
            )

        plan_id = self.request.GET.get("plan", "").strip()
        if plan_id.isdigit():
            queryset = queryset.filter(plan_id=int(plan_id))

        community_id = self.request.GET.get("community", "").strip()
        if community_id.isdigit():
            queryset = queryset.filter(community_id=int(community_id))

        return queryset.order_by("-completed_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["log_form"] = kwargs.get("log_form") or WorkoutLogForm(user=self.request.user)
        logs_queryset = context["logs"]
        context["insights"] = self._build_insights(logs_queryset)
        context["rpe_trend"] = self._build_rpe_trend(logs_queryset)
        context["filter_options"] = self._filter_options()
        context["selected_filters"] = {
            "days": self.request.GET.get("days", "all").strip() or "all",
            "plan": self.request.GET.get("plan", "").strip(),
            "community": self.request.GET.get("community", "").strip(),
            "trend_days": str(self._trend_days_filter()),
        }
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

    def _build_insights(self, logs):
        now = timezone.now()
        recent_7d = logs.filter(completed_at__gte=now - timedelta(days=7))
        recent_14d_rpe = logs.filter(
            completed_at__gte=now - timedelta(days=14),
            perceived_exertion__isnull=False,
        )
        recent_30d_communities = logs.filter(
            completed_at__gte=now - timedelta(days=30),
            community__isnull=False,
        )
        avg_rpe_14d = recent_14d_rpe.aggregate(avg=Avg("perceived_exertion"))["avg"]

        return {
            "total_logs": logs.count(),
            "recent_logs_7d": recent_7d.count(),
            "avg_rpe_14d": avg_rpe_14d,
            "active_communities_30d": recent_30d_communities.values(
                "community_id"
            ).distinct().count(),
        }

    def _window_days_filter(self):
        value = self.request.GET.get("days", "").strip().lower()
        if not value or value == "all":
            return None
        if not value.isdigit():
            return None
        parsed = int(value)
        if parsed not in self.WINDOW_DAYS_OPTIONS:
            return None
        return parsed

    def _trend_days_filter(self):
        value = self.request.GET.get("trend_days", "").strip().lower()
        if not value or not value.isdigit():
            return 14
        parsed = int(value)
        if parsed not in self.TREND_DAYS_OPTIONS:
            return 14
        return parsed

    def _build_rpe_trend(self, logs):
        trend_days = self._trend_days_filter()
        now = timezone.now()
        cutoff = now - timedelta(days=trend_days)
        points = list(
            logs.filter(
                completed_at__gte=cutoff,
                perceived_exertion__isnull=False,
            )
            .annotate(day=TruncDate("completed_at"))
            .values("day")
            .annotate(avg_rpe=Avg("perceived_exertion"), entry_count=Count("id"))
            .order_by("day")
        )

        for point in points:
            avg_rpe = point["avg_rpe"]
            if avg_rpe is None:
                point["height_pct"] = 0
            else:
                point["height_pct"] = int(round(float(avg_rpe) * 10))

        current_avg = logs.filter(
            completed_at__gte=cutoff,
            perceived_exertion__isnull=False,
        ).aggregate(avg=Avg("perceived_exertion"))["avg"]
        previous_start = cutoff - timedelta(days=trend_days)
        previous_avg = logs.filter(
            completed_at__gte=previous_start,
            completed_at__lt=cutoff,
            perceived_exertion__isnull=False,
        ).aggregate(avg=Avg("perceived_exertion"))["avg"]

        delta = None
        direction = "flat"
        if current_avg is not None and previous_avg is not None:
            delta = float(current_avg) - float(previous_avg)
            if delta > 0:
                direction = "up"
            elif delta < 0:
                direction = "down"

        compare = {
            "current_avg": current_avg,
            "previous_avg": previous_avg,
            "delta": delta,
            "direction": direction,
        }

        return {
            "window_days": trend_days,
            "points": points,
            "compare": compare,
        }

    def _filter_options(self):
        base_logs = WorkoutLog.objects.filter(performed_by=self.request.user)
        plans = WorkoutPlan.objects.filter(
            id__in=base_logs.values_list("plan_id", flat=True)
        ).order_by("name")
        communities = Community.objects.filter(
            id__in=base_logs.values_list("community_id", flat=True)
        ).order_by("name")
        return {
            "days": self.WINDOW_DAYS_OPTIONS,
            "trend_days": self.TREND_DAYS_OPTIONS,
            "plans": plans,
            "communities": communities,
        }
