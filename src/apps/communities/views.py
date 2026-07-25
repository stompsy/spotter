from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from apps.moderation.models import ModerationDecision, ModerationRecord
from apps.notifications.models import NotificationEvent, NotificationType

from .models import (
    Community,
    CommunityInvitation,
    CommunityJoinRequest,
    CommunityMembership,
    CommunityVisibility,
    JoinRequestStatus,
    MembershipRole,
    MembershipStatus,
)


class CommunityListView(ListView):
    model = Community
    template_name = "communities/list.html"
    context_object_name = "communities"

    def get_queryset(self):
        queryset = Community.objects.filter(is_archived=False)
        user = self.request.user
        if user.is_authenticated:
            membership_community_ids = CommunityMembership.objects.filter(
                user=user,
                status=MembershipStatus.ACTIVE,
            ).values_list("community_id", flat=True)
            return queryset.filter(
                Q(visibility=CommunityVisibility.PUBLIC) | Q(id__in=membership_community_ids)
            ).order_by("name")
        return queryset.filter(visibility=CommunityVisibility.PUBLIC).order_by("name")


class CommunityDetailView(DetailView):
    model = Community
    template_name = "communities/detail.html"
    context_object_name = "community"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        community = super().get_object(queryset)
        if community.visibility == CommunityVisibility.PUBLIC:
            return community

        user = self.request.user
        if not user.is_authenticated:
            raise Http404("Community not found")

        is_member = CommunityMembership.objects.filter(
            community=community,
            user=user,
            status=MembershipStatus.ACTIVE,
        ).exists()
        if not is_member:
            raise Http404("Community not found")
        return community

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        community = self.object

        membership = None
        if user.is_authenticated:
            membership = CommunityMembership.objects.filter(
                community=community,
                user=user,
            ).first()
            pending_join_request = CommunityJoinRequest.objects.filter(
                community=community,
                requested_by=user,
                status=JoinRequestStatus.PENDING,
            ).first()
        else:
            pending_join_request = None

        can_moderate = self._can_moderate_community(user, community, membership)
        pending_requests = CommunityJoinRequest.objects.filter(
            community=community,
            status=JoinRequestStatus.PENDING,
        ).select_related("requested_by")
        active_invitations = CommunityInvitation.objects.filter(
            community=community,
            accepted_at__isnull=True,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

        context["membership"] = membership
        context["pending_join_request"] = pending_join_request
        context["can_moderate"] = can_moderate
        context["can_invite"] = can_moderate and community.visibility == CommunityVisibility.PRIVATE
        context["active_invitations"] = active_invitations.order_by("-created_at")[:5]
        context["pending_requests"] = pending_requests if can_moderate else []
        return context

    @staticmethod
    def _can_moderate_community(
        user,
        community: Community,
        membership: CommunityMembership | None,
    ) -> bool:
        if not user.is_authenticated:
            return False
        if community.created_by_id == user.id:
            return True
        if not membership or membership.status != MembershipStatus.ACTIVE:
            return False
        return membership.role in {MembershipRole.OWNER, MembershipRole.MODERATOR}


class CommunityJoinRequestCreateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        community = get_object_or_404(Community, slug=slug, is_archived=False)

        membership = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
        ).first()

        if membership and membership.status == MembershipStatus.ACTIVE:
            return self._response(request, community, membership, pending_join_request=None)

        pending_request = CommunityJoinRequest.objects.filter(
            community=community,
            requested_by=request.user,
            status=JoinRequestStatus.PENDING,
        ).first()

        if not pending_request:
            pending_request = CommunityJoinRequest.objects.create(
                community=community,
                requested_by=request.user,
                message=request.POST.get("message", "").strip(),
                status=JoinRequestStatus.PENDING,
            )
            self._notify_join_request_submitted(community, pending_request)

        membership, _ = CommunityMembership.objects.get_or_create(
            community=community,
            user=request.user,
            defaults={
                "status": MembershipStatus.PENDING,
            },
        )
        if membership.status in {MembershipStatus.REJECTED, MembershipStatus.LEFT}:
            membership.status = MembershipStatus.PENDING
            membership.save(update_fields=["status"])

        return self._response(request, community, membership, pending_join_request=pending_request)

    def _response(
        self,
        request: HttpRequest,
        community: Community,
        membership: CommunityMembership | None,
        pending_join_request: CommunityJoinRequest | None,
    ) -> HttpResponse:
        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "communities/partials/membership_card.html",
                {
                    "community": community,
                    "membership": membership,
                    "pending_join_request": pending_join_request,
                },
            )
        return redirect("communities:detail", slug=community.slug)

    @staticmethod
    def _notify_join_request_submitted(
        community: Community,
        join_request: CommunityJoinRequest,
    ) -> None:
        reviewer_ids = set(
            CommunityMembership.objects.filter(
                community=community,
                status=MembershipStatus.ACTIVE,
                role__in={MembershipRole.OWNER, MembershipRole.MODERATOR},
            ).values_list("user_id", flat=True)
        )
        reviewer_ids.add(community.created_by_id)
        reviewer_ids.discard(join_request.requested_by_id)

        user_model = get_user_model()
        recipients = list(user_model.objects.filter(id__in=reviewer_ids))
        for recipient in recipients:
            NotificationEvent.objects.create(
                recipient=recipient,
                notification_type=NotificationType.JOIN_REQUEST,
                subject=f"New join request: {community.name}",
                body=(
                    f"{join_request.requested_by} requested access to "
                    f"{community.name}."
                ),
                payload={
                    "community_id": community.id,
                    "join_request_id": join_request.id,
                    "requested_by_id": join_request.requested_by_id,
                },
            )


class CommunityJoinRequestReviewView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str, join_request_id: int) -> HttpResponse:
        community = get_object_or_404(Community, slug=slug, is_archived=False)
        join_request = get_object_or_404(
            CommunityJoinRequest,
            id=join_request_id,
            community=community,
            status=JoinRequestStatus.PENDING,
        )

        membership = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
        ).first()
        can_moderate = CommunityDetailView._can_moderate_community(
            request.user,
            community,
            membership,
        )
        if not can_moderate:
            raise Http404("Join request not found")

        decision = request.POST.get("decision", "").strip().lower()
        if decision not in {JoinRequestStatus.APPROVED, JoinRequestStatus.REJECTED}:
            raise Http404("Decision not found")

        join_request.status = decision
        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        member_record, _ = CommunityMembership.objects.get_or_create(
            community=community,
            user=join_request.requested_by,
            defaults={
                "status": MembershipStatus.PENDING,
            },
        )
        if decision == JoinRequestStatus.APPROVED:
            member_record.status = MembershipStatus.ACTIVE
            member_record.joined_at = timezone.now()
        else:
            member_record.status = MembershipStatus.REJECTED
        member_record.save(update_fields=["status", "joined_at"])

        ModerationRecord.objects.create(
            target_type="community_join_request",
            target_id=str(join_request.id),
            decision=(
                ModerationDecision.APPROVED
                if decision == JoinRequestStatus.APPROVED
                else ModerationDecision.REJECTED
            ),
            reason=request.POST.get("reason", "").strip(),
            decided_by=request.user,
            payload={
                "community_id": community.id,
                "request_user_id": join_request.requested_by_id,
            },
        )
        NotificationEvent.objects.create(
            recipient=join_request.requested_by,
            notification_type=NotificationType.JOIN_DECISION,
            subject=f"Join request update: {community.name}",
            body=(
                "Your request was approved."
                if decision == JoinRequestStatus.APPROVED
                else "Your request was not approved."
            ),
            payload={
                "community_id": community.id,
                "join_request_id": join_request.id,
                "decision": decision,
            },
        )

        pending_requests = CommunityJoinRequest.objects.filter(
            community=community,
            status=JoinRequestStatus.PENDING,
        ).select_related("requested_by")

        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "communities/partials/moderation_queue.html",
                {
                    "community": community,
                    "pending_requests": pending_requests,
                    "can_moderate": True,
                },
            )

        return redirect("communities:detail", slug=community.slug)


class CommunityInvitationCreateView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        community = get_object_or_404(Community, slug=slug, is_archived=False)
        membership = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
        ).first()
        can_moderate = CommunityDetailView._can_moderate_community(
            request.user,
            community,
            membership,
        )
        if not can_moderate or community.visibility != CommunityVisibility.PRIVATE:
            raise Http404("Community not found")

        invited_email = request.POST.get("invited_email", "").strip()
        expires_days_raw = request.POST.get("expires_days", "7").strip()
        try:
            expires_days = int(expires_days_raw)
        except ValueError:
            expires_days = 7
        expires_days = min(max(expires_days, 1), 30)

        invitation = CommunityInvitation.objects.create(
            community=community,
            invited_email=invited_email,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(days=expires_days),
        )
        NotificationEvent.objects.create(
            recipient=request.user,
            notification_type=NotificationType.MODERATION_DECISION,
            subject=f"Invitation created: {community.name}",
            body=f"Invite code {invitation.invite_code} is ready to share.",
            payload={
                "community_id": community.id,
                "invite_code": str(invitation.invite_code),
                "invited_email": invited_email,
            },
        )

        if request.headers.get("HX-Request") == "true":
            active_invitations = CommunityInvitation.objects.filter(
                community=community,
                accepted_at__isnull=True,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            return render(
                request,
                "communities/partials/invitation_panel.html",
                {
                    "community": community,
                    "can_invite": True,
                    "active_invitations": active_invitations.order_by("-created_at")[:5],
                },
            )

        return redirect("communities:detail", slug=community.slug)


class CommunityInvitationAcceptView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, invite_code) -> HttpResponse:
        invitation = get_object_or_404(CommunityInvitation, invite_code=invite_code)
        now = timezone.now()
        if invitation.expires_at and invitation.expires_at <= now:
            raise Http404("Invitation expired")
        if (
            invitation.invited_email
            and invitation.invited_email.lower() != request.user.email.lower()
        ):
            raise Http404("Invitation not found")

        membership, _ = CommunityMembership.objects.get_or_create(
            community=invitation.community,
            user=request.user,
            defaults={
                "role": MembershipRole.MEMBER,
                "status": MembershipStatus.ACTIVE,
                "joined_at": now,
            },
        )
        if membership.status != MembershipStatus.ACTIVE:
            membership.status = MembershipStatus.ACTIVE
            if membership.joined_at is None:
                membership.joined_at = now
            membership.save(update_fields=["status", "joined_at"])

        if invitation.accepted_at is None:
            invitation.accepted_at = now
            invitation.save(update_fields=["accepted_at"])

        NotificationEvent.objects.create(
            recipient=request.user,
            notification_type=NotificationType.JOIN_DECISION,
            subject=f"Invitation accepted: {invitation.community.name}",
            body="You joined the community via invitation.",
            payload={
                "community_id": invitation.community_id,
                "invite_code": str(invitation.invite_code),
            },
        )
        return redirect("communities:detail", slug=invitation.community.slug)
