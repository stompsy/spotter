from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views import View
from django.views.generic import DetailView, ListView

from apps.communities.models import CommunityMembership, MembershipRole, MembershipStatus

from .forms import (
    ExerciseForm,
    ExerciseMediaForm,
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
    ExerciseEquipmentRequirement,
    ExerciseMediaType,
    ExerciseMovementType,
    WorkoutPlan,
    WorkoutPlanAssignment,
)


class ExerciseListView(LoginRequiredMixin, ListView):
    model = Exercise
    template_name = "workouts/exercises.html"
    context_object_name = "exercises"

    def get_queryset(self):
        return Exercise.objects.prefetch_related("media_items").order_by("name")

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
        context["exercise_media_type_choices"] = ExerciseMediaType.choices
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
        return context

    def post(self, request: HttpRequest) -> HttpResponse:
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
        context["assignment_form"] = kwargs.get("assignment_form") or WorkoutPlanAssignmentForm(
            user=self.request.user
        )
        context["plan_form"] = kwargs.get("plan_form") or WorkoutPlanForm(
            instance=self.object,
            user=self.request.user,
        )
        context["can_manage"] = _can_manage_plan(self.request.user, self.object)
        context["items"] = self.object.items.select_related("exercise").all()
        context["challenge_days"] = self.object.challenge_days.all()
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
