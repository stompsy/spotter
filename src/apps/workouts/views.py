from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views import View
from django.views.generic import DetailView, ListView

from apps.communities.models import CommunityMembership, MembershipRole, MembershipStatus

from .forms import (
    ChallengeWizardForm,
    ExerciseForm,
    ExerciseMediaForm,
    WorkoutChallengeDayCompletionForm,
    WorkoutPlanAssignmentForm,
    WorkoutPlanForm,
    WorkoutPlanItemForm,
)
from .models import (
    CurationStatus,
    Exercise,
    ExerciseBodyArea,
    ExerciseCandidate,
    ExerciseCandidateDecision,
    ExerciseCategory,
    ExerciseDifficultyLevel,
    ExerciseDurationFit,
    ExerciseEquipmentRequirement,
    ExerciseMediaType,
    ExerciseMovementType,
    WorkoutChallengeDay,
    WorkoutChallengeDayCompletion,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanDurationBand,
    WorkoutPlanItem,
    WorkoutPlanType,
)

CHALLENGE_PRESET_OPTIONS = [
    {
        "key": "abs_30_day",
        "label": "30-Day Core Challenge",
        "description": (
            "Internally authored core progression with daily focus and copy-safe notes."
        ),
    },
    {
        "key": "lunge_30_day",
        "label": "30-Day Lunge Challenge",
        "description": (
            "Internally authored lower-body progression with daily lunge practice "
            "and recovery pacing."
        ),
    },
]


GUIDED_PLAN_COMPOSER_TEMPLATES = [
    {
        "key": "starter_suggested",
        "label": "Suggested Starter",
        "description": (
            "Automatically choose short, medium, or long starter cards based on "
            "duration profile and available exercises."
        ),
    },
    {
        "key": "starter_short",
        "label": "Short Session Starter",
        "description": "Add 3 reusable exercise cards tuned for short sessions.",
    },
    {
        "key": "starter_medium",
        "label": "Medium Session Starter",
        "description": "Add 5 reusable exercise cards for balanced medium sessions.",
    },
    {
        "key": "starter_long",
        "label": "Long Session Starter",
        "description": "Add 7 reusable exercise cards for longer training blocks.",
    },
    {
        "key": "challenge_day_starter",
        "label": "Challenge Day Starter",
        "description": "Attach a starter card set to the next available challenge day.",
        "challenge_only": True,
    },
]


COMPOSER_TEMPLATE_CONFIG = {
    "starter_short": {
        "duration_fit": ExerciseDurationFit.SHORT,
        "target_count": 3,
        "repetitions": "3 x 8",
    },
    "starter_medium": {
        "duration_fit": ExerciseDurationFit.MEDIUM,
        "target_count": 5,
        "repetitions": "3 x 10",
    },
    "starter_long": {
        "duration_fit": ExerciseDurationFit.LONG,
        "target_count": 7,
        "repetitions": "4 x 12",
    },
}


class ExerciseListView(LoginRequiredMixin, ListView):
    model = Exercise
    template_name = "workouts/exercises.html"
    context_object_name = "exercises"

    def get_queryset(self):
        queryset = Exercise.objects.prefetch_related("media_items")

        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(instructions__icontains=search_query)
                | Q(coaching_cues__icontains=search_query)
            )

        filter_specs = {
            "movement_type": (
                "movement_type",
                {choice[0] for choice in ExerciseMovementType.choices},
            ),
            "primary_body_area": (
                "primary_body_area",
                {choice[0] for choice in ExerciseBodyArea.choices},
            ),
            "equipment_requirement": (
                "equipment_requirement",
                {choice[0] for choice in ExerciseEquipmentRequirement.choices},
            ),
            "difficulty_level": (
                "difficulty_level",
                {choice[0] for choice in ExerciseDifficultyLevel.choices},
            ),
            "duration_fit": (
                "duration_fit",
                {choice[0] for choice in ExerciseDurationFit.choices},
            ),
        }
        for query_param, (field_name, allowed_values) in filter_specs.items():
            selected_value = self.request.GET.get(query_param, "all").strip().lower()
            if selected_value != "all" and selected_value in allowed_values:
                queryset = queryset.filter(**{field_name: selected_value})

        sort = self.request.GET.get("sort", "name_asc").strip().lower()
        if sort == "name_desc":
            return queryset.order_by("-name")
        if sort == "movement_type":
            return queryset.order_by("movement_type", "name")
        if sort == "body_area":
            return queryset.order_by("primary_body_area", "name")
        if sort == "equipment":
            return queryset.order_by("equipment_requirement", "name")
        if sort == "difficulty":
            difficulty_order = Case(
                When(difficulty_level=ExerciseDifficultyLevel.BEGINNER, then=Value(0)),
                When(difficulty_level=ExerciseDifficultyLevel.INTERMEDIATE, then=Value(1)),
                When(difficulty_level=ExerciseDifficultyLevel.ADVANCED, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
            return queryset.order_by(difficulty_order, "name")
        if sort == "duration_fit":
            duration_order = Case(
                When(duration_fit=ExerciseDurationFit.SHORT, then=Value(0)),
                When(duration_fit=ExerciseDurationFit.MEDIUM, then=Value(1)),
                When(duration_fit=ExerciseDurationFit.LONG, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
            return queryset.order_by(duration_order, "name")

        return queryset.order_by("name")

    def _get_filtered_candidates(self):
        status = self.request.GET.get("candidate_status", "all").strip().lower()
        confidence_band = self.request.GET.get("confidence_band", "all").strip().lower()
        publish_readiness = self.request.GET.get("publish_readiness", "all").strip().lower()

        queryset = ExerciseCandidate.objects.select_related("source", "reviewed_by")

        allowed_statuses = {choice[0] for choice in CurationStatus.choices}
        if status != "all" and status in allowed_statuses:
            queryset = queryset.filter(status=status)
        else:
            status = "all"

        if confidence_band == "high":
            queryset = queryset.filter(confidence__gte=0.85)
        elif confidence_band == "medium":
            queryset = queryset.filter(confidence__gte=0.60, confidence__lt=0.85)
        elif confidence_band == "low":
            queryset = queryset.filter(confidence__lt=0.60)
        else:
            confidence_band = "all"

        if publish_readiness not in {"all", "ready", "missing"}:
            publish_readiness = "all"

        return (
            queryset.order_by("status", "-confidence", "normalized_name", "id"),
            status,
            confidence_band,
            publish_readiness,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        (
            candidates,
            selected_status,
            selected_confidence_band,
            selected_publish_readiness,
        ) = self._get_filtered_candidates()
        candidates = list(candidates)
        for candidate in candidates:
            candidate.publish_requirements_missing = _get_publish_requirements_missing(
                candidate
            )
            candidate.publish_confirmation_audit = _get_publish_confirmation_audit(candidate)

        if selected_publish_readiness == "ready":
            candidates = [
                candidate
                for candidate in candidates
                if not candidate.publish_requirements_missing
            ]
        elif selected_publish_readiness == "missing":
            candidates = [
                candidate
                for candidate in candidates
                if candidate.publish_requirements_missing
            ]

        recent_decisions = ExerciseCandidateDecision.objects.select_related(
            "candidate",
            "decided_by",
        )[:12]
        context["exercise_form"] = kwargs.get("exercise_form") or ExerciseForm()
        context["exercise_media_form"] = kwargs.get("exercise_media_form") or ExerciseMediaForm()
        context["exercise_category_choices"] = ExerciseCategory.choices
        context["exercise_movement_type_choices"] = ExerciseMovementType.choices
        context["exercise_body_area_choices"] = ExerciseBodyArea.choices
        context["exercise_difficulty_level_choices"] = ExerciseDifficultyLevel.choices
        context["exercise_equipment_requirement_choices"] = (
            ExerciseEquipmentRequirement.choices
        )
        context["exercise_duration_fit_choices"] = ExerciseDurationFit.choices
        context["exercise_media_type_choices"] = ExerciseMediaType.choices
        context["selected_exercise_query"] = self.request.GET.get("q", "").strip()
        context["selected_movement_type"] = self.request.GET.get(
            "movement_type", "all"
        ).strip().lower()
        context["selected_primary_body_area"] = self.request.GET.get(
            "primary_body_area", "all"
        ).strip().lower()
        context["selected_equipment_requirement"] = self.request.GET.get(
            "equipment_requirement", "all"
        ).strip().lower()
        context["selected_difficulty_level"] = self.request.GET.get(
            "difficulty_level", "all"
        ).strip().lower()
        context["selected_duration_fit"] = self.request.GET.get(
            "duration_fit", "all"
        ).strip().lower()
        context["selected_exercise_sort"] = self.request.GET.get(
            "sort", "name_asc"
        ).strip().lower()
        context["exercise_sort_options"] = [
            {"value": "name_asc", "label": "Name A-Z"},
            {"value": "name_desc", "label": "Name Z-A"},
            {"value": "movement_type", "label": "Movement type"},
            {"value": "body_area", "label": "Body area"},
            {"value": "equipment", "label": "Equipment"},
            {"value": "difficulty", "label": "Difficulty"},
            {"value": "duration_fit", "label": "Duration fit"},
        ]
        context["can_review_candidates"] = _can_review_candidates(self.request.user)
        context["candidates"] = candidates
        context["recent_candidate_decisions"] = recent_decisions
        context["selected_candidate_status"] = selected_status
        context["selected_confidence_band"] = selected_confidence_band
        context["selected_publish_readiness"] = selected_publish_readiness
        context["candidate_status_options"] = [
            {"value": "all", "label": "All statuses"},
            *[
                {"value": value, "label": label}
                for value, label in CurationStatus.choices
            ],
        ]
        context["confidence_band_options"] = [
            {"value": "all", "label": "All confidence"},
            {"value": "high", "label": "High (>= 0.85)"},
            {"value": "medium", "label": "Medium (0.60-0.84)"},
            {"value": "low", "label": "Low (< 0.60)"},
        ]
        context["publish_readiness_options"] = [
            {"value": "all", "label": "All candidates"},
            {"value": "ready", "label": "Publish ready"},
            {"value": "missing", "label": "Missing requirements"},
        ]
        return context

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ExerciseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Exercise created.")
            return redirect("workouts:exercises")

        response = self.render_to_response(self.get_context_data(exercise_form=form))
        response.status_code = 400
        return response


class ExerciseUpdateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, exercise_id: int) -> HttpResponse:
        exercise = get_object_or_404(Exercise, id=exercise_id)
        form = ExerciseForm(request.POST, instance=exercise)
        if form.is_valid():
            form.save()
            messages.success(request, "Exercise updated.")
        else:
            messages.error(request, "Exercise update failed.")
        return redirect("workouts:exercises")


class ExerciseToggleActiveView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, exercise_id: int) -> HttpResponse:
        exercise = get_object_or_404(Exercise, id=exercise_id)
        exercise.is_active = not exercise.is_active
        exercise.save(update_fields=["is_active"])
        messages.success(
            request,
            "Exercise activated." if exercise.is_active else "Exercise archived.",
        )
        return redirect("workouts:exercises")


class ExerciseMediaCreateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, exercise_id: int) -> HttpResponse:
        exercise = get_object_or_404(Exercise, id=exercise_id)
        form = ExerciseMediaForm(request.POST, request.FILES)
        if form.is_valid():
            media_item = form.save(commit=False)
            media_item.exercise = exercise
            media_item.save()
            messages.success(request, "Exercise media added.")
        else:
            messages.error(request, "Exercise media could not be added.")
        return redirect("workouts:exercises")


class ExerciseCandidateReviewActionView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, candidate_id: int) -> HttpResponse:
        if not _can_review_candidates(request.user):
            raise Http404("Candidate not found")

        candidate = get_object_or_404(ExerciseCandidate, id=candidate_id)
        action = request.POST.get("action", "").strip().lower()
        reason = request.POST.get("reason", "").strip()
        next_url = request.POST.get("next", "").strip()
        previous_status = candidate.status
        metadata_updates = _extract_candidate_metadata_updates(request)

        if metadata_updates is not None:
            metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
            candidate.metadata = _merge_candidate_metadata_with_audit(
                metadata,
                metadata_updates,
                request.user,
            )

        action_map = {
            "mark_review": CurationStatus.NEEDS_REVIEW,
            "send_back": CurationStatus.DRAFT,
            "approve": CurationStatus.APPROVED,
            "publish": CurationStatus.PUBLISHED,
            "deprecate": CurationStatus.DEPRECATED,
        }
        new_status = action_map.get(action)
        if new_status is None:
            raise Http404("Candidate action not found")

        redirect_target = "workouts:exercises"
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            redirect_target = next_url

        try:
            candidate.transition_to(new_status)
        except ValidationError as exc:
            message = " ".join(exc.messages).strip() if exc.messages else ""
            messages.error(
                request,
                message or "Candidate status transition is not allowed.",
            )
            return redirect(redirect_target)

        candidate.reviewed_by = request.user
        candidate.reviewed_at = timezone.now()
        candidate.decision_reason = reason
        candidate.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "decision_reason",
                "metadata",
                "updated_at",
            ]
        )
        ExerciseCandidateDecision.objects.create(
            candidate=candidate,
            action=action,
            from_status=previous_status,
            to_status=new_status,
            decided_by=request.user,
            reason=reason,
        )
        messages.success(request, f"Candidate moved to {new_status}.")
        return redirect(redirect_target)


class WorkoutPlanListView(LoginRequiredMixin, ListView):
    model = WorkoutPlan
    template_name = "workouts/list.html"
    context_object_name = "plans"

    def get_queryset(self):
        community_ids = CommunityMembership.objects.filter(
            user=self.request.user,
            status=MembershipStatus.ACTIVE,
        ).values_list("community_id", flat=True)
        return (
            WorkoutPlan.objects.filter(
                Q(created_by=self.request.user) | Q(community_id__in=community_ids)
            )
            .distinct()
            .select_related("community", "created_by")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plan_form"] = kwargs.get("plan_form") or WorkoutPlanForm(user=self.request.user)
        context["challenge_wizard_form"] = (
            kwargs.get("challenge_wizard_form") or ChallengeWizardForm()
        )
        context["challenge_preset_options"] = CHALLENGE_PRESET_OPTIONS
        return context

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action", "").strip().lower()
        if action == "challenge_wizard":
            challenge_wizard_form = ChallengeWizardForm(request.POST)
            if challenge_wizard_form.is_valid():
                plan = _create_challenge_plan_from_wizard(
                    request.user,
                    challenge_wizard_form.cleaned_data,
                )
                messages.success(request, f"Challenge wizard created: {plan.name}.")
                return redirect("workouts:detail", slug=plan.slug)

            self.object_list = self.get_queryset()
            response = self.render_to_response(
                self.get_context_data(challenge_wizard_form=challenge_wizard_form)
            )
            response.status_code = 400
            return response

        preset_key = request.POST.get("preset_key", "").strip().lower()
        if preset_key:
            try:
                plan = _create_challenge_preset_plan(request.user, preset_key)
            except ValueError:
                messages.error(request, "Unknown preset selection.")
                return redirect("workouts:list")

            messages.success(request, f"Preset created: {plan.name}.")
            return redirect("workouts:detail", slug=plan.slug)

        form = WorkoutPlanForm(request.POST, user=request.user)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.created_by = request.user
            plan.slug = _build_unique_plan_slug(plan.name)
            plan.save()
            messages.success(request, "Workout plan created.")
            return redirect("workouts:detail", slug=plan.slug)

        self.object_list = self.get_queryset()
        response = self.render_to_response(self.get_context_data(plan_form=form))
        response.status_code = 400
        return response


class WorkoutPlanDetailView(LoginRequiredMixin, DetailView):
    model = WorkoutPlan
    template_name = "workouts/detail.html"
    context_object_name = "plan"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        plan = super().get_object(queryset)
        if not _can_view_plan(self.request.user, plan):
            raise Http404("Workout plan not found")
        return plan

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item_form"] = kwargs.get("item_form") or WorkoutPlanItemForm()
        context["completion_form"] = (
            kwargs.get("completion_form")
            or WorkoutChallengeDayCompletionForm(plan=self.object)
        )
        context["assignment_form"] = kwargs.get("assignment_form") or WorkoutPlanAssignmentForm(
            user=self.request.user
        )
        context["plan_form"] = kwargs.get("plan_form") or WorkoutPlanForm(
            instance=self.object,
            user=self.request.user,
        )
        context["can_manage"] = _can_manage_plan(self.request.user, self.object)
        suggested_key = _get_suggested_composer_template_key(self.object)
        context["composer_template_options"] = _get_composer_template_options(self.object)
        context["composer_suggested_template_key"] = suggested_key
        context["composer_suggestion_message"] = _build_composer_suggestion_message(
            self.object,
            suggested_key,
        )
        context["phases"] = self.object.phases.all()
        context["items"] = self.object.items.select_related("exercise").all()
        challenge_days = list(self.object.challenge_days.all())
        _annotate_challenge_day_completion_state(
            challenge_days,
            plan=self.object,
            user=self.request.user,
        )
        context["challenge_days"] = challenge_days
        context["assignments"] = self.object.assignments.select_related(
            "assigned_to", "assigned_community"
        ).order_by("-created_at")
        return context


class WorkoutPlanUpdateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_manage_plan(request.user, plan):
            raise Http404("Workout plan not found")

        original_name = plan.name
        form = WorkoutPlanForm(request.POST, instance=plan, user=request.user)
        if form.is_valid():
            updated_plan = form.save(commit=False)
            if updated_plan.name != original_name:
                updated_plan.slug = _build_unique_plan_slug(updated_plan.name)
            updated_plan.save()
            messages.success(request, "Plan updated.")
            return redirect("workouts:detail", slug=updated_plan.slug)

        detail_view = WorkoutPlanDetailView()
        detail_view.request = request
        detail_view.object = plan
        response = render(
            request,
            "workouts/detail.html",
            detail_view.get_context_data(plan_form=form),
        )
        response.status_code = 400
        return response


class WorkoutPlanCloneView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        source_plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_view_plan(request.user, source_plan):
            raise Http404("Workout plan not found")

        clone_name = request.POST.get("clone_name", "").strip() or f"{source_plan.name} Copy"
        cloned_plan = WorkoutPlan.objects.create(
            name=clone_name,
            slug=_build_unique_plan_slug(clone_name),
            description=source_plan.description,
            created_by=request.user,
            community=source_plan.community,
            is_template=source_plan.is_template,
            is_published=False,
        )
        items = list(source_plan.items.all())
        for item in items:
            item.pk = None
            item.plan = cloned_plan
            item.save()

        messages.success(request, "Plan cloned.")
        return redirect("workouts:detail", slug=cloned_plan.slug)


class WorkoutPlanPublishToggleView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_manage_plan(request.user, plan):
            raise Http404("Workout plan not found")

        plan.is_published = not plan.is_published
        plan.save(update_fields=["is_published"])
        messages.success(
            request,
            "Plan published." if plan.is_published else "Plan unpublished.",
        )
        return redirect("workouts:detail", slug=plan.slug)


class WorkoutPlanItemCreateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_manage_plan(request.user, plan):
            raise Http404("Workout plan not found")

        form = WorkoutPlanItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.plan = plan
            if not item.order:
                current_max = plan.items.order_by("-order").values_list("order", flat=True).first()
                item.order = (current_max or 0) + 1
            item.save()
            messages.success(request, "Exercise added to plan.")
            return redirect("workouts:detail", slug=plan.slug)

        detail_view = WorkoutPlanDetailView()
        detail_view.request = request
        detail_view.object = plan
        response = render(
            request,
            "workouts/detail.html",
            detail_view.get_context_data(item_form=form),
        )
        response.status_code = 400
        return response


class WorkoutChallengeDayCompletionCreateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_view_plan(request.user, plan):
            raise Http404("Workout plan not found")
        if plan.plan_type != WorkoutPlanType.CHALLENGE:
            raise Http404("Challenge completion is only available for challenge plans")

        form = WorkoutChallengeDayCompletionForm(request.POST, plan=plan)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.completed_by = request.user
            completion.save()
            messages.success(request, "Challenge progress logged.")
            return redirect("workouts:detail", slug=plan.slug)

        detail_view = WorkoutPlanDetailView()
        detail_view.request = request
        detail_view.object = plan
        response = render(
            request,
            "workouts/detail.html",
            detail_view.get_context_data(completion_form=form),
        )
        response.status_code = 400
        return response


class WorkoutPlanComposeTemplateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_manage_plan(request.user, plan):
            raise Http404("Workout plan not found")

        template_key = request.POST.get("template_key", "").strip().lower()
        try:
            created_count = _apply_plan_composer_template(plan, template_key)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("workouts:detail", slug=plan.slug)

        messages.success(request, f"Guided template added {created_count} item(s).")
        return redirect("workouts:detail", slug=plan.slug)


class WorkoutPlanAssignView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        if not _can_manage_plan(request.user, plan):
            raise Http404("Workout plan not found")

        form = WorkoutPlanAssignmentForm(request.POST, user=request.user)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.plan = plan
            assignment.save()
            messages.success(request, "Plan assigned successfully.")
            return redirect("workouts:detail", slug=plan.slug)

        detail_view = WorkoutPlanDetailView()
        detail_view.request = request
        detail_view.object = plan
        response = render(
            request,
            "workouts/detail.html",
            detail_view.get_context_data(assignment_form=form),
        )
        response.status_code = 400
        return response


class WorkoutPlanAssignmentStateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str, assignment_id: int) -> HttpResponse:
        plan = get_object_or_404(WorkoutPlan, slug=slug)
        assignment = get_object_or_404(
            WorkoutPlanAssignment,
            id=assignment_id,
            plan=plan,
        )
        if not _can_manage_plan(request.user, plan):
            raise Http404("Workout assignment not found")

        action = request.POST.get("action", "").strip().lower()
        if action == "pause":
            assignment.is_active = False
            assignment.paused_at = timezone.now()
            assignment.ended_at = None
            assignment.save(update_fields=["is_active", "paused_at", "ended_at"])
            messages.success(request, "Assignment paused.")
        elif action == "resume":
            assignment.is_active = True
            assignment.paused_at = None
            assignment.ended_at = None
            assignment.save(update_fields=["is_active", "paused_at", "ended_at"])
            messages.success(request, "Assignment resumed.")
        elif action == "end":
            assignment.is_active = False
            assignment.ended_at = timezone.now()
            assignment.paused_at = None
            assignment.save(update_fields=["is_active", "ended_at", "paused_at"])
            messages.success(request, "Assignment ended.")
        else:
            raise Http404("Assignment action not found")

        return redirect("workouts:detail", slug=plan.slug)


def _build_unique_plan_slug(name: str) -> str:
    base_slug = slugify(name) or "workout-plan"
    slug = base_slug
    suffix = 1
    while WorkoutPlan.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    return slug


def _get_composer_template_options(plan: WorkoutPlan) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for template in GUIDED_PLAN_COMPOSER_TEMPLATES:
        if template.get("challenge_only") and plan.plan_type != WorkoutPlanType.CHALLENGE:
            continue
        options.append(template)
    return options


def _apply_plan_composer_template(plan: WorkoutPlan, template_key: str) -> int:
    resolved_template_key = template_key
    if template_key == "starter_suggested":
        resolved_template_key = _get_suggested_composer_template_key(plan)

    if resolved_template_key in COMPOSER_TEMPLATE_CONFIG:
        template_config = COMPOSER_TEMPLATE_CONFIG[resolved_template_key]
        duration_fit = template_config["duration_fit"]
        target_count = template_config["target_count"]
        repetitions = template_config["repetitions"]
        exercises = _select_composer_exercises(plan, duration_fit, target_count)
        if not exercises:
            raise ValueError("No active exercises available for that guided template.")

        next_order = _next_plan_order(plan)
        for index, exercise in enumerate(exercises):
            WorkoutPlanItem.objects.create(
                plan=plan,
                exercise=exercise,
                order=next_order + index,
                repetitions=repetitions,
                notes="Guided composer template item.",
            )
        return len(exercises)

    if template_key == "challenge_day_starter":
        if plan.plan_type != WorkoutPlanType.CHALLENGE:
            raise ValueError("Challenge day templates are only available for challenge plans.")
        day = _next_available_challenge_day(plan)
        if day is None:
            raise ValueError("No challenge days are configured for this plan.")

        exercises = _select_composer_exercises(plan, ExerciseDurationFit.SHORT, 2)
        if not exercises:
            raise ValueError("No active exercises available for that guided template.")

        next_order = _next_plan_order(plan)
        for index, exercise in enumerate(exercises):
            WorkoutPlanItem.objects.create(
                plan=plan,
                challenge_day=day,
                exercise=exercise,
                order=next_order + index,
                repetitions="3 x 8 each side",
                notes=f"Guided challenge day template for day {day.day_number}.",
            )
        return len(exercises)

    raise ValueError("Unknown guided template.")


def _get_suggested_composer_template_key(plan: WorkoutPlan) -> str:
    preferred_key = _duration_band_template_key(plan.duration_band)
    existing_ids = set(plan.items.values_list("exercise_id", flat=True))
    if not Exercise.objects.filter(is_active=True).exclude(id__in=existing_ids).exists():
        return preferred_key

    best_key = preferred_key
    best_score = (-1.0, -1.0, -1)
    for template_key, template_config in COMPOSER_TEMPLATE_CONFIG.items():
        target_count = template_config["target_count"]
        duration_fit = template_config["duration_fit"]

        matching_count = Exercise.objects.filter(
            is_active=True,
            duration_fit=duration_fit,
        ).exclude(id__in=existing_ids).count()
        unspecified_count = Exercise.objects.filter(
            is_active=True,
            duration_fit=ExerciseDurationFit.UNSPECIFIED,
        ).exclude(id__in=existing_ids).count()
        fit_pool_count = matching_count + unspecified_count

        adequacy_score = min(fit_pool_count / target_count, 1.0)
        specificity_score = min(matching_count / target_count, 1.0)
        band_alignment = 1 if template_key == preferred_key else 0
        score = (adequacy_score, specificity_score, band_alignment)
        if score > best_score:
            best_score = score
            best_key = template_key

    return best_key


def _duration_band_template_key(duration_band: str) -> str:
    band_map = {
        WorkoutPlanDurationBand.SHORT: "starter_short",
        WorkoutPlanDurationBand.MEDIUM: "starter_medium",
        WorkoutPlanDurationBand.LONG: "starter_long",
    }
    return band_map.get(duration_band, "starter_short")


def _build_composer_suggestion_message(plan: WorkoutPlan, suggested_key: str) -> str:
    option = next(
        (
            template
            for template in GUIDED_PLAN_COMPOSER_TEMPLATES
            if template["key"] == suggested_key
        ),
        None,
    )
    suggested_label = option["label"] if option else "Short Session Starter"
    preferred_key = _duration_band_template_key(plan.duration_band)
    if suggested_key == preferred_key:
        return f"Recommended for this {plan.get_duration_band_display().lower()} plan."
    return (
        f"Recommended now: {suggested_label}. "
        "This suggestion adapts to currently available exercise cards."
    )


def _next_plan_order(plan: WorkoutPlan) -> int:
    current_max = plan.items.order_by("-order").values_list("order", flat=True).first()
    return (current_max or 0) + 1


def _select_composer_exercises(
    plan: WorkoutPlan,
    duration_fit: str,
    target_count: int,
) -> list[Exercise]:
    existing_ids = set(plan.items.values_list("exercise_id", flat=True))
    querysets = [
        Exercise.objects.filter(
            is_active=True,
            duration_fit=duration_fit,
        ).exclude(id__in=existing_ids),
        Exercise.objects.filter(
            is_active=True,
            duration_fit=ExerciseDurationFit.UNSPECIFIED,
        ).exclude(id__in=existing_ids),
        Exercise.objects.filter(is_active=True).exclude(id__in=existing_ids),
    ]

    selected: list[Exercise] = []
    seen_ids: set[int] = set()
    for queryset in querysets:
        for exercise in queryset.order_by("name"):
            if exercise.id in seen_ids:
                continue
            selected.append(exercise)
            seen_ids.add(exercise.id)
            if len(selected) >= target_count:
                return selected
    return selected


def _next_available_challenge_day(plan: WorkoutPlan) -> WorkoutChallengeDay | None:
    challenge_days = plan.challenge_days.order_by("day_number", "id")
    for day in challenge_days:
        if not day.items.exists():
            return day
    return challenge_days.first()


def _create_challenge_plan_from_wizard(user, data: dict[str, object]) -> WorkoutPlan:
    focus_area = str(data["focus_area"]).strip()
    duration_days = int(data["duration_days"])
    progression_style = str(data["progression_style"])
    checkpoint_interval_days = int(data["checkpoint_interval_days"])

    plan_name = f"{duration_days}-Day {focus_area} Challenge"
    plan = WorkoutPlan.objects.create(
        name=plan_name,
        slug=_build_unique_plan_slug(plan_name),
        description=(
            f"Guided challenge wizard plan focused on {focus_area.lower()} with "
            f"{_progression_style_label(progression_style).lower()} and "
            f"checkpoints every {checkpoint_interval_days} days."
        ),
        created_by=user,
        plan_type=WorkoutPlanType.CHALLENGE,
        duration_band=_duration_band_for_challenge_days(duration_days),
        challenge_duration_days=duration_days,
        challenge_focus_area=focus_area,
        is_template=False,
        is_published=False,
    )

    base_duration = _challenge_base_duration_minutes(plan.duration_band)
    for day_number in range(1, duration_days + 1):
        checkpoint_due = (
            day_number % checkpoint_interval_days == 0 or day_number == duration_days
        )
        progression_delta = _challenge_progression_delta(
            progression_style,
            day_number,
            duration_days,
        )
        target_duration = max(base_duration + progression_delta, 8)

        notes = _challenge_day_progression_note(progression_style)
        if checkpoint_due:
            notes = (
                f"{notes} Checkpoint: log completion quality and update the next block."
            )

        WorkoutChallengeDay.objects.create(
            plan=plan,
            day_number=day_number,
            title=f"Day {day_number}",
            focus_area=focus_area,
            target_duration_minutes=target_duration,
            notes=notes,
        )

    return plan


def _duration_band_for_challenge_days(duration_days: int) -> str:
    if duration_days <= 21:
        return WorkoutPlanDurationBand.SHORT
    if duration_days <= 42:
        return WorkoutPlanDurationBand.MEDIUM
    return WorkoutPlanDurationBand.LONG


def _challenge_base_duration_minutes(duration_band: str) -> int:
    if duration_band == WorkoutPlanDurationBand.MEDIUM:
        return 18
    if duration_band == WorkoutPlanDurationBand.LONG:
        return 26
    return 12


def _challenge_progression_delta(
    progression_style: str,
    day_number: int,
    duration_days: int,
) -> int:
    if progression_style == "linear":
        return int(((day_number - 1) / max(duration_days - 1, 1)) * 8)
    if progression_style == "step":
        return ((day_number - 1) // 7) * 2

    wave_cycle = [0, 2, 1, 3, 1, 2, 0]
    return wave_cycle[(day_number - 1) % len(wave_cycle)]


def _progression_style_label(progression_style: str) -> str:
    labels = {
        "linear": "Linear build",
        "step": "Step-up blocks",
        "wave": "Wave loading",
    }
    return labels.get(progression_style, "Linear build")


def _challenge_day_progression_note(progression_style: str) -> str:
    notes = {
        "linear": "Progression: add a small amount of work while maintaining form.",
        "step": "Progression: hold intensity in blocks, then step up workload.",
        "wave": "Progression: alternate harder and easier days to manage recovery.",
    }
    return notes.get(
        progression_style,
        "Progression: add a small amount of work while maintaining form.",
    )


def _annotate_challenge_day_completion_state(
    challenge_days: list[WorkoutChallengeDay],
    *,
    plan: WorkoutPlan,
    user,
) -> None:
    for day in challenge_days:
        day.user_completed_minutes = 0
        day.user_split_count = 0
        day.user_completion_state = "not_started"

    if plan.plan_type != WorkoutPlanType.CHALLENGE or not challenge_days:
        return

    completion_rows = (
        WorkoutChallengeDayCompletion.objects.filter(
            challenge_day__plan=plan,
            completed_by=user,
        )
        .values("challenge_day_id")
        .annotate(
            completed_minutes=Sum("completed_minutes"),
            split_count=Count("id"),
        )
    )
    completion_by_day_id = {
        row["challenge_day_id"]: row
        for row in completion_rows
    }

    for day in challenge_days:
        row = completion_by_day_id.get(day.id)
        if row is None:
            continue

        day.user_completed_minutes = int(row["completed_minutes"] or 0)
        day.user_split_count = int(row["split_count"] or 0)
        target_minutes = day.target_duration_minutes or 0
        if target_minutes > 0 and day.user_completed_minutes >= target_minutes:
            day.user_completion_state = "complete"
        else:
            day.user_completion_state = "partial"


def _create_challenge_preset_plan(user, preset_key: str) -> WorkoutPlan:
    preset_builders = {
        "abs_30_day": _build_core_challenge_preset,
        "lunge_30_day": _build_lunge_challenge_preset,
    }
    builder = preset_builders.get(preset_key)
    if builder is None:
        raise ValueError("Unknown preset")

    with transaction.atomic():
        return builder(user)


def _build_core_challenge_preset(user) -> WorkoutPlan:
    exercises = [
        _get_or_create_preset_exercise(
            name="Hollow Hold",
            category=ExerciseCategory.CORE_STABILITY,
            movement_type=ExerciseMovementType.CORE,
            primary_body_area=ExerciseBodyArea.CORE,
            difficulty_level=ExerciseDifficultyLevel.BEGINNER,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Braced hold for trunk stiffness and anterior core control.",
            instructions="Brace, tuck the ribs down, and hold a steady breathing rhythm.",
            safety_notes="Stop if the lower back cannot stay gently grounded.",
            coaching_cues="Exhale, brace, and keep tension even front to back.",
        ),
        _get_or_create_preset_exercise(
            name="Dead Bug",
            category=ExerciseCategory.CORE_STABILITY,
            movement_type=ExerciseMovementType.CORE,
            primary_body_area=ExerciseBodyArea.CORE,
            difficulty_level=ExerciseDifficultyLevel.BEGINNER,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Alternating limb pattern for core coordination and control.",
            instructions="Move slowly and keep the trunk quiet while each limb reaches.",
            safety_notes="Reduce range if the ribs flare or the lower back lifts.",
            coaching_cues="Reach long, breathe out, and move one side at a time.",
        ),
        _get_or_create_preset_exercise(
            name="Forearm Plank",
            category=ExerciseCategory.CORE_STABILITY,
            movement_type=ExerciseMovementType.CORE,
            primary_body_area=ExerciseBodyArea.CORE,
            difficulty_level=ExerciseDifficultyLevel.BEGINNER,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Front plank variation for isometric trunk endurance.",
            instructions="Stack shoulders over elbows and keep the pelvis level.",
            safety_notes="End the set if the hips sag or the shoulders shrug upward.",
            coaching_cues="Squeeze glutes, brace the stomach, and push the floor away.",
        ),
        _get_or_create_preset_exercise(
            name="Reverse Crunch",
            category=ExerciseCategory.CORE_STABILITY,
            movement_type=ExerciseMovementType.CORE,
            primary_body_area=ExerciseBodyArea.CORE,
            difficulty_level=ExerciseDifficultyLevel.BEGINNER,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Curling trunk pattern for lower-abdominal control.",
            instructions="Tuck the pelvis first and move with deliberate tempo.",
            safety_notes="Keep the motion smooth and avoid swinging the legs.",
            coaching_cues="Curl slowly, pause briefly, and lower with control.",
        ),
    ]
    plan = WorkoutPlan.objects.create(
        name="30-Day Core Challenge",
        slug=_build_unique_plan_slug("30-Day Core Challenge"),
        description=(
            "Copy-safe internal preset that builds core control across 30 days with "
            "steady progression, light recovery, and repeatable practice."
        ),
        created_by=user,
        plan_type=WorkoutPlanType.CHALLENGE,
        duration_band=WorkoutPlanDurationBand.SHORT,
        challenge_duration_days=30,
        challenge_focus_area="Core",
        is_template=True,
        is_published=False,
    )
    _populate_challenge_plan(
        plan,
        exercises,
        focus_area="Core",
        notes_by_stage={
            "foundation": "Prioritize breathing, trunk stiffness, and repeatable positions.",
            "build": "Add controlled volume without sacrificing bracing quality.",
            "finish": "Maintain crisp technique while the daily demand rises slightly.",
        },
    )
    return plan


def _build_lunge_challenge_preset(user) -> WorkoutPlan:
    exercises = [
        _get_or_create_preset_exercise(
            name="Bodyweight Lunge",
            category=ExerciseCategory.STRENGTH,
            movement_type=ExerciseMovementType.LUNGE,
            primary_body_area=ExerciseBodyArea.LOWER_BODY,
            difficulty_level=ExerciseDifficultyLevel.BEGINNER,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Foundational lunge pattern for lower-body control and balance.",
            instructions="Step with control, drop straight down, and stand smoothly.",
            safety_notes="Keep the front foot planted and shorten range if balance slips.",
            coaching_cues="Tall chest, quiet knee, and push through the whole foot.",
        ),
        _get_or_create_preset_exercise(
            name="Reverse Lunge",
            category=ExerciseCategory.STRENGTH,
            movement_type=ExerciseMovementType.LUNGE,
            primary_body_area=ExerciseBodyArea.LOWER_BODY,
            difficulty_level=ExerciseDifficultyLevel.BEGINNER,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Rear-stepping lunge variation for controlled deceleration.",
            instructions="Step back softly and keep the front leg stable through the rep.",
            safety_notes="Use a smaller step if the hips twist or the front heel lifts.",
            coaching_cues="Reach back quietly, stay stacked, and drive up with intent.",
        ),
        _get_or_create_preset_exercise(
            name="Split Squat Hold",
            category=ExerciseCategory.STRENGTH,
            movement_type=ExerciseMovementType.LUNGE,
            primary_body_area=ExerciseBodyArea.LOWER_BODY,
            difficulty_level=ExerciseDifficultyLevel.INTERMEDIATE,
            equipment_requirement=ExerciseEquipmentRequirement.NONE,
            duration_fit=ExerciseDurationFit.SHORT,
            description="Isometric split-stance hold for balance and positional strength.",
            instructions=(
                "Sink to a strong split stance and hold with even pressure through both legs."
            ),
            safety_notes="Come higher if the back knee or front foot loses stable alignment.",
            coaching_cues="Stay tall, brace the trunk, and keep both legs active.",
        ),
        _get_or_create_preset_exercise(
            name="Walking Lunge",
            category=ExerciseCategory.CONDITIONING,
            movement_type=ExerciseMovementType.LUNGE,
            primary_body_area=ExerciseBodyArea.LOWER_BODY,
            difficulty_level=ExerciseDifficultyLevel.INTERMEDIATE,
            equipment_requirement=ExerciseEquipmentRequirement.MINIMAL,
            duration_fit=ExerciseDurationFit.MEDIUM,
            description="Continuous lunge pattern for coordination, posture, and stamina.",
            instructions="Move forward under control and reset balance before each next step.",
            safety_notes="Use shorter steps if posture collapses or the front knee drifts.",
            coaching_cues="Step long enough to stay stable and finish tall each rep.",
        ),
    ]
    plan = WorkoutPlan.objects.create(
        name="30-Day Lunge Challenge",
        slug=_build_unique_plan_slug("30-Day Lunge Challenge"),
        description=(
            "Copy-safe internal preset that builds lunge capacity, balance, and lower-body "
            "tolerance across 30 days with repeatable technique cues."
        ),
        created_by=user,
        plan_type=WorkoutPlanType.CHALLENGE,
        duration_band=WorkoutPlanDurationBand.SHORT,
        challenge_duration_days=30,
        challenge_focus_area="Lower body",
        is_template=True,
        is_published=False,
    )
    _populate_challenge_plan(
        plan,
        exercises,
        focus_area="Lower body",
        notes_by_stage={
            "foundation": "Focus on stance, balance, and smooth vertical control.",
            "build": "Increase repetition tolerance while keeping each rep symmetrical.",
            "finish": "Keep posture crisp as the daily lower-body workload gradually rises.",
        },
    )
    return plan


def _populate_challenge_plan(
    plan: WorkoutPlan,
    exercises: list[Exercise],
    focus_area: str,
    notes_by_stage: dict[str, str],
) -> None:
    for day_number in range(1, 31):
        if day_number <= 10:
            stage = "foundation"
            title = f"Foundation {day_number}"
            target_duration = 8
        elif day_number <= 20:
            stage = "build"
            title = f"Build {day_number - 10}"
            target_duration = 10
        else:
            stage = "finish"
            title = f"Finish {day_number - 20}"
            target_duration = 12

        day = WorkoutChallengeDay.objects.create(
            plan=plan,
            day_number=day_number,
            title=title,
            focus_area=focus_area,
            target_duration_minutes=target_duration,
            notes=notes_by_stage[stage],
        )
        exercise = exercises[(day_number - 1) % len(exercises)]
        WorkoutPlanItem.objects.create(
            plan=plan,
            challenge_day=day,
            exercise=exercise,
            order=day_number,
            repetitions=_build_preset_repetition_text(day_number, exercise.name),
            notes=f"Day {day_number} priority: smooth, repeatable {focus_area.lower()} work.",
        )


def _build_preset_repetition_text(day_number: int, exercise_name: str) -> str:
    if "Hold" in exercise_name or "Plank" in exercise_name:
        seconds = 20 + ((day_number - 1) // 5) * 5
        return f"3 x {seconds}s"

    reps = 8 + ((day_number - 1) // 5) * 2
    if "Dead Bug" in exercise_name or "Lunge" in exercise_name or "Split Squat" in exercise_name:
        return f"3 x {reps} each side"
    return f"3 x {reps}"


def _get_or_create_preset_exercise(
    *,
    name: str,
    category: str,
    movement_type: str,
    primary_body_area: str,
    difficulty_level: str,
    equipment_requirement: str,
    duration_fit: str,
    description: str,
    instructions: str,
    safety_notes: str,
    coaching_cues: str,
) -> Exercise:
    slug = slugify(name) or "exercise"
    exercise, _ = Exercise.objects.get_or_create(
        slug=slug,
        defaults={
            "name": name,
            "category": category,
            "movement_type": movement_type,
            "primary_body_area": primary_body_area,
            "difficulty_level": difficulty_level,
            "equipment_requirement": equipment_requirement,
            "duration_fit": duration_fit,
            "description": description,
            "instructions": instructions,
            "safety_notes": safety_notes,
            "coaching_cues": coaching_cues,
            "is_active": True,
        },
    )
    return exercise


def _can_manage_plan(user, plan: WorkoutPlan) -> bool:
    if plan.created_by_id == user.id:
        return True
    if not plan.community_id:
        return False
    membership = CommunityMembership.objects.filter(
        community_id=plan.community_id,
        user=user,
        status=MembershipStatus.ACTIVE,
    ).first()
    if membership is None:
        return False
    return membership.role in {MembershipRole.OWNER, MembershipRole.MODERATOR}


def _can_view_plan(user, plan: WorkoutPlan) -> bool:
    if plan.created_by_id == user.id:
        return True
    if not plan.community_id:
        return False
    return CommunityMembership.objects.filter(
        community_id=plan.community_id,
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists()


def _can_review_candidates(user) -> bool:
    return user.is_superuser or user.has_perm("workouts.review_exercisecandidate")


def _extract_candidate_metadata_updates(request: HttpRequest) -> dict[str, object] | None:
    helper_text_keys = ["source_name", "source_url", "attribution_text"]
    helper_flag_keys = [
        "media_rights_confirmed",
        "content_rewritten",
        "safety_reviewed",
    ]

    if not any(key in request.POST for key in helper_text_keys + helper_flag_keys):
        return None

    updates: dict[str, object] = {
        "source_name": request.POST.get("source_name", "").strip(),
        "source_url": request.POST.get("source_url", "").strip(),
        "attribution_text": request.POST.get("attribution_text", "").strip(),
    }
    for key in helper_flag_keys:
        updates[key] = key in request.POST
    return updates


def _merge_candidate_metadata_with_audit(
    metadata: dict[str, object],
    updates: dict[str, object],
    user,
) -> dict[str, object]:
    merged = dict(metadata)
    now = timezone.now().isoformat()
    username = user.get_username() or str(user.pk)

    auditable_keys = [
        "source_name",
        "source_url",
        "attribution_text",
        "media_rights_confirmed",
        "content_rewritten",
        "safety_reviewed",
    ]

    for key, value in updates.items():
        merged[key] = value
        if key not in auditable_keys:
            continue

        confirmed_at_key = f"{key}_confirmed_at"
        confirmed_by_key = f"{key}_confirmed_by"

        is_confirmed = bool(value)
        if isinstance(value, str):
            is_confirmed = bool(value.strip())

        if is_confirmed:
            merged[confirmed_at_key] = now
            merged[confirmed_by_key] = username
        else:
            merged.pop(confirmed_at_key, None)
            merged.pop(confirmed_by_key, None)

    return merged


def _missing_publish_metadata_fields(metadata: object) -> list[str]:
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    required_text_fields = [
        "source_name",
        "source_url",
        "attribution_text",
    ]
    required_true_flags = [
        "media_rights_confirmed",
        "content_rewritten",
        "safety_reviewed",
    ]

    missing_text_fields = [
        key
        for key in required_text_fields
        if not str(metadata_dict.get(key, "")).strip()
    ]
    missing_true_flags = [
        key
        for key in required_true_flags
        if metadata_dict.get(key) is not True
    ]
    return missing_text_fields + missing_true_flags


def _get_publish_requirements_missing(candidate: ExerciseCandidate) -> list[str]:
    missing_items = []
    if not candidate.source.is_approved:
        missing_items.append("approved source")
    if not candidate.source.license_name.strip():
        missing_items.append("source license")

    metadata_labels = {
        "source_name": "source name",
        "source_url": "source URL",
        "attribution_text": "attribution text",
        "media_rights_confirmed": "media rights confirmation",
        "content_rewritten": "content rewritten confirmation",
        "safety_reviewed": "safety review confirmation",
    }
    for field_name in _missing_publish_metadata_fields(candidate.metadata):
        missing_items.append(metadata_labels[field_name])

    return missing_items


def _get_publish_confirmation_audit(candidate: ExerciseCandidate) -> list[str]:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    entries = []
    field_labels = {
        "source_name": "Source name",
        "source_url": "Source URL",
        "attribution_text": "Attribution text",
        "media_rights_confirmed": "Media rights",
        "content_rewritten": "Content rewritten",
        "safety_reviewed": "Safety reviewed",
    }

    for key, label in field_labels.items():
        confirmed_at = metadata.get(f"{key}_confirmed_at")
        confirmed_by = metadata.get(f"{key}_confirmed_by")
        if not confirmed_at or not confirmed_by:
            continue
        entries.append(f"{label}: {confirmed_by} at {confirmed_at}")

    return entries
