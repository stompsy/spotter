import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.communities.models import Community, CommunityMembership, MembershipStatus
from apps.workouts.models import (
    WorkoutChallengeDayCompletion,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanType,
)

from .forms import WorkoutLogForm
from .models import WorkoutLog


class ProgressFiltersMixin:
    WINDOW_DAYS_OPTIONS = [7, 14, 30, 90]
    TREND_DAYS_OPTIONS = [7, 14, 30]

    def _filtered_logs_queryset(self):
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

        return queryset

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


class WorkoutLogListCreateView(LoginRequiredMixin, ProgressFiltersMixin, ListView):
    model = WorkoutLog
    template_name = "progress/logs.html"
    context_object_name = "logs"

    def get_queryset(self):
        return self._filtered_logs_queryset().order_by("-completed_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["log_form"] = kwargs.get("log_form") or WorkoutLogForm(user=self.request.user)
        logs_queryset = context["logs"]
        context["insights"] = self._build_insights(logs_queryset)
        context["challenge_kpis"] = self._build_challenge_kpis()
        context["rpe_trend"] = self._build_rpe_trend(logs_queryset)
        context["filter_options"] = self._filter_options()
        context["selected_filters"] = {
            "days": self.request.GET.get("days", "all").strip() or "all",
            "plan": self.request.GET.get("plan", "").strip(),
            "community": self.request.GET.get("community", "").strip(),
            "trend_days": str(self._trend_days_filter()),
        }
        context["active_querystring"] = self.request.GET.urlencode()
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

    def _build_challenge_kpis(self):
        today = timezone.localdate()
        active_community_ids = set(
            CommunityMembership.objects.filter(
                user=self.request.user,
                status=MembershipStatus.ACTIVE,
            ).values_list("community_id", flat=True)
        )
        assignments = list(
            WorkoutPlanAssignment.objects.filter(
                plan__plan_type=WorkoutPlanType.CHALLENGE,
                starts_on__isnull=False,
                is_active=True,
                ended_at__isnull=True,
            )
            .filter(
                Q(assigned_to=self.request.user)
                | Q(assigned_community_id__in=active_community_ids)
            )
            .select_related("plan")
            .order_by("starts_on", "id")
        )

        if not assignments:
            return {
                "has_data": False,
                "scheduled_elapsed_days": 0,
                "completed_days": 0,
                "adherence_pct": None,
                "current_streak": 0,
                "best_streak": 0,
                "baseline_pct": None,
                "current_pct": None,
                "delta_pct": None,
                "checkpoints": [],
            }

        plan_ids = {assignment.plan_id for assignment in assignments}
        completion_rows = (
            WorkoutChallengeDayCompletion.objects.filter(
                completed_by=self.request.user,
                challenge_day__plan_id__in=plan_ids,
            )
            .values("challenge_day_id")
            .annotate(total_minutes=Sum("completed_minutes"))
        )
        completion_by_day_id = {
            row["challenge_day_id"]: int(row["total_minutes"] or 0)
            for row in completion_rows
        }

        scheduled_elapsed_days = 0
        completed_days = 0
        completion_sequence: list[bool] = []
        baseline_ratio = None
        current_ratio = None
        checkpoints = []

        for assignment in assignments:
            challenge_days = list(
                assignment.plan.challenge_days.order_by("day_number", "id")
            )
            checkpoint_history_for_plan = []
            for challenge_day in challenge_days:
                scheduled_date = assignment.starts_on + timedelta(
                    days=challenge_day.day_number - 1
                )
                if scheduled_date > today:
                    continue

                target_minutes = challenge_day.target_duration_minutes or 0
                completed_minutes = completion_by_day_id.get(challenge_day.id, 0)
                completion_ratio = 0.0
                is_complete = False
                if target_minutes > 0:
                    completion_ratio = min((completed_minutes / target_minutes) * 100.0, 100.0)
                    is_complete = completed_minutes >= target_minutes

                scheduled_elapsed_days += 1
                completion_sequence.append(is_complete)
                if is_complete:
                    completed_days += 1

                if baseline_ratio is None:
                    baseline_ratio = completion_ratio
                current_ratio = completion_ratio

                if "checkpoint" in (challenge_day.notes or "").lower() and target_minutes > 0:
                    checkpoint_delta = None
                    if checkpoint_history_for_plan:
                        checkpoint_delta = completion_ratio - checkpoint_history_for_plan[-1]
                    checkpoint_history_for_plan.append(completion_ratio)
                    checkpoints.append(
                        {
                            "plan_name": assignment.plan.name,
                            "day_number": challenge_day.day_number,
                            "scheduled_date": scheduled_date,
                            "completion_pct": completion_ratio,
                            "delta_pct": checkpoint_delta,
                        }
                    )

        adherence_pct = None
        if scheduled_elapsed_days > 0:
            adherence_pct = (completed_days / scheduled_elapsed_days) * 100.0

        best_streak = 0
        running_streak = 0
        for is_complete in completion_sequence:
            if is_complete:
                running_streak += 1
                best_streak = max(best_streak, running_streak)
            else:
                running_streak = 0

        current_streak = 0
        for is_complete in reversed(completion_sequence):
            if not is_complete:
                break
            current_streak += 1

        delta_pct = None
        if baseline_ratio is not None and current_ratio is not None:
            delta_pct = current_ratio - baseline_ratio

        return {
            "has_data": True,
            "scheduled_elapsed_days": scheduled_elapsed_days,
            "completed_days": completed_days,
            "adherence_pct": adherence_pct,
            "current_streak": current_streak,
            "best_streak": best_streak,
            "baseline_pct": baseline_ratio,
            "current_pct": current_ratio,
            "delta_pct": delta_pct,
            "checkpoints": checkpoints,
        }

class WorkoutLogExportCsvView(LoginRequiredMixin, ProgressFiltersMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        logs = self._filtered_logs_queryset().order_by("-completed_at")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="progress-logs.csv"'

        writer = csv.writer(response)
        writer.writerow(["completed_at", "plan", "community", "perceived_exertion", "notes"])
        for log in logs:
            writer.writerow(
                [
                    timezone.localtime(log.completed_at).strftime("%Y-%m-%d %H:%M:%S"),
                    log.plan.name if log.plan else "",
                    log.community.name if log.community else "",
                    log.perceived_exertion if log.perceived_exertion is not None else "",
                    log.notes,
                ]
            )
        return response


class WorkoutTrendExportCsvView(LoginRequiredMixin, ProgressFiltersMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        logs = self._filtered_logs_queryset()
        trend = self._build_rpe_trend(logs)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="progress-trend.csv"'

        writer = csv.writer(response)
        writer.writerow(["day", "avg_rpe", "entry_count", "height_pct", "window_days"])
        for point in trend["points"]:
            writer.writerow(
                [
                    point["day"],
                    point["avg_rpe"],
                    point["entry_count"],
                    point["height_pct"],
                    trend["window_days"],
                ]
            )
        return response
