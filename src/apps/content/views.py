from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from apps.communities.models import CommunityMembership, MembershipRole, MembershipStatus
from apps.moderation.models import ModerationDecision, ModerationRecord
from apps.notifications.models import NotificationEvent, NotificationType

from .forms import GuidanceContentForm
from .models import ContentStatus, GuidanceContent


class GuidanceListView(LoginRequiredMixin, ListView):
    model = GuidanceContent
    template_name = "guidance/list.html"
    context_object_name = "guidance_items"

    def get_queryset(self):
        moderated_community_ids = _moderated_community_ids(self.request.user)
        return (
            GuidanceContent.objects.filter(
                Q(status=ContentStatus.APPROVED)
                | Q(author=self.request.user)
                | Q(community_id__in=moderated_community_ids)
            )
            .select_related("author", "community")
            .order_by("-submitted_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = context["guidance_items"]
        context["guidance_form"] = kwargs.get("guidance_form") or GuidanceContentForm(
            user=self.request.user
        )
        context["pending_items"] = items.filter(status=ContentStatus.PENDING)
        context["published_items"] = items.filter(status=ContentStatus.APPROVED)
        context["my_items"] = items.filter(author=self.request.user)
        return context

    def post(self, request: HttpRequest) -> HttpResponse:
        form = GuidanceContentForm(request.POST, user=request.user)
        if form.is_valid():
            guidance = form.save(commit=False)
            guidance.author = request.user
            guidance.status = ContentStatus.DRAFT
            guidance.save()
            messages.success(request, "Guidance draft created.")
            return redirect("guidance:detail", guidance_id=guidance.id)

        response = self.render_to_response(self.get_context_data(guidance_form=form))
        response.status_code = 400
        return response


class GuidanceDetailView(LoginRequiredMixin, DetailView):
    model = GuidanceContent
    template_name = "guidance/detail.html"
    context_object_name = "guidance"
    pk_url_kwarg = "guidance_id"

    def get_object(self, queryset=None):
        guidance = super().get_object(queryset)
        if not _can_view_guidance(self.request.user, guidance):
            raise Http404("Guidance not found")
        return guidance

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guidance = self.object
        can_moderate = _can_moderate_guidance(self.request.user, guidance)
        context["can_moderate"] = can_moderate
        context["can_edit"] = guidance.author_id == self.request.user.id and guidance.status in {
            ContentStatus.DRAFT,
            ContentStatus.REJECTED,
        }
        context["can_submit"] = guidance.author_id == self.request.user.id and guidance.status in {
            ContentStatus.DRAFT,
            ContentStatus.REJECTED,
        }
        context["can_publish"] = can_moderate and guidance.status == ContentStatus.APPROVED
        context["guidance_form"] = kwargs.get("guidance_form") or GuidanceContentForm(
            instance=guidance,
            user=self.request.user,
        )
        context["moderation_history"] = ModerationRecord.objects.filter(
            target_type="guidance_content",
            target_id=str(guidance.id),
        ).select_related("decided_by").order_by("-decided_at")
        return context


class GuidanceUpdateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, guidance_id: int) -> HttpResponse:
        guidance = get_object_or_404(GuidanceContent, id=guidance_id)
        if guidance.author_id != request.user.id or guidance.status not in {
            ContentStatus.DRAFT,
            ContentStatus.REJECTED,
        }:
            raise Http404("Guidance not found")

        form = GuidanceContentForm(request.POST, instance=guidance, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Guidance draft updated.")
            return redirect("guidance:detail", guidance_id=guidance.id)

        detail_view = GuidanceDetailView()
        detail_view.request = request
        detail_view.object = guidance
        response = render(
            request,
            "guidance/detail.html",
            detail_view.get_context_data(guidance_form=form),
        )
        response.status_code = 400
        return response


class GuidanceSubmitView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, guidance_id: int) -> HttpResponse:
        guidance = get_object_or_404(GuidanceContent, id=guidance_id)
        if guidance.author_id != request.user.id or guidance.status not in {
            ContentStatus.DRAFT,
            ContentStatus.REJECTED,
        }:
            raise Http404("Guidance not found")
        if guidance.community_id is None:
            messages.error(request, "Assign a community before submitting for review.")
            return redirect("guidance:detail", guidance_id=guidance.id)

        guidance.status = ContentStatus.PENDING
        guidance.published_at = None
        guidance.save(update_fields=["status", "published_at"])
        messages.success(request, "Guidance submitted for moderation.")
        return redirect("guidance:detail", guidance_id=guidance.id)


class GuidanceModerateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, guidance_id: int) -> HttpResponse:
        guidance = get_object_or_404(GuidanceContent, id=guidance_id, status=ContentStatus.PENDING)
        if not _can_moderate_guidance(request.user, guidance):
            raise Http404("Guidance not found")

        decision = request.POST.get("decision", "").strip().lower()
        reason = request.POST.get("reason", "").strip()
        if decision == ModerationDecision.APPROVED:
            guidance.status = ContentStatus.APPROVED
        elif decision == ModerationDecision.REJECTED:
            guidance.status = ContentStatus.REJECTED
        elif decision == ModerationDecision.NEEDS_CHANGES:
            guidance.status = ContentStatus.DRAFT
        else:
            raise Http404("Decision not found")

        guidance.published_at = None
        guidance.save(update_fields=["status", "published_at"])

        ModerationRecord.objects.create(
            target_type="guidance_content",
            target_id=str(guidance.id),
            decision=decision,
            reason=reason,
            decided_by=request.user,
            payload={
                "community_id": guidance.community_id,
                "guidance_id": guidance.id,
            },
        )
        NotificationEvent.objects.create(
            recipient=guidance.author,
            notification_type=NotificationType.MODERATION_DECISION,
            subject=f"Guidance review update: {guidance.title}",
            body=f"Decision: {decision.replace('_', ' ')}",
            payload={
                "guidance_id": guidance.id,
                "decision": decision,
            },
        )
        messages.success(request, "Moderation decision recorded.")
        return redirect("guidance:detail", guidance_id=guidance.id)


class GuidancePublishView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, guidance_id: int) -> HttpResponse:
        guidance = get_object_or_404(GuidanceContent, id=guidance_id, status=ContentStatus.APPROVED)
        if not _can_moderate_guidance(request.user, guidance):
            raise Http404("Guidance not found")

        guidance.published_at = timezone.now()
        guidance.save(update_fields=["published_at"])
        if guidance.author_id != request.user.id:
            NotificationEvent.objects.create(
                recipient=guidance.author,
                notification_type=NotificationType.MODERATION_DECISION,
                subject=f"Guidance published: {guidance.title}",
                body="Your approved guidance is now published.",
                payload={"guidance_id": guidance.id, "decision": "published"},
            )
        messages.success(request, "Guidance published.")
        return redirect("guidance:detail", guidance_id=guidance.id)


def _moderated_community_ids(user) -> list[int]:
    if not user.is_authenticated:
        return []
    return list(
        CommunityMembership.objects.filter(
            user=user,
            status=MembershipStatus.ACTIVE,
            role__in={MembershipRole.OWNER, MembershipRole.MODERATOR},
        ).values_list("community_id", flat=True)
    )


def _can_moderate_guidance(user, guidance: GuidanceContent) -> bool:
    if not user.is_authenticated:
        return False
    if guidance.community_id is None:
        return False
    return guidance.community_id in _moderated_community_ids(user)


def _can_view_guidance(user, guidance: GuidanceContent) -> bool:
    if guidance.status == ContentStatus.APPROVED and guidance.published_at is not None:
        return True
    if not user.is_authenticated:
        return False
    if guidance.author_id == user.id:
        return True
    return _can_moderate_guidance(user, guidance)
