from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import DetailView, ListView

from apps.communities.models import CommunityMembership, MembershipRole, MembershipStatus

from .forms import ExerciseForm, WorkoutPlanAssignmentForm, WorkoutPlanForm, WorkoutPlanItemForm
from .models import Exercise, WorkoutPlan, WorkoutPlanAssignment


class ExerciseListView(LoginRequiredMixin, ListView):
    model = Exercise
    template_name = "workouts/exercises.html"
    context_object_name = "exercises"

    def get_queryset(self):
        return Exercise.objects.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exercise_form"] = kwargs.get("exercise_form") or ExerciseForm()
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
