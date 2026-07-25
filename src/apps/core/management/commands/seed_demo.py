from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.communities.models import (
    Community,
    CommunityJoinRequest,
    CommunityMembership,
    CommunityVisibility,
    JoinRequestStatus,
    MembershipRole,
    MembershipStatus,
)
from apps.content.models import ContentStatus, GuidanceContent, GuidanceTopic
from apps.moderation.models import ModerationDecision, ModerationRecord
from apps.notifications.models import DeliveryStatus, NotificationEvent, NotificationType
from apps.progress.models import WorkoutLog
from apps.workouts.models import (
    Exercise,
    ExerciseCategory,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanItem,
)


class Command(BaseCommand):
    help = "Seed demo data for local MVP walkthroughs. Safe to run multiple times."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="spotter123",
            help="Password to set for demo accounts (default: spotter123)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        user_model = get_user_model()

        users = {
            "platform_admin": self._upsert_user(
                user_model,
                username="platform_admin",
                email="admin@spotter.local",
                display_name="Platform Admin",
                password=password,
                is_staff=True,
                is_superuser=True,
            ),
            "coach_maya": self._upsert_user(
                user_model,
                username="coach_maya",
                email="maya@spotter.local",
                display_name="Coach Maya",
                password=password,
                is_staff=False,
                is_superuser=False,
            ),
            "mod_eli": self._upsert_user(
                user_model,
                username="mod_eli",
                email="eli@spotter.local",
                display_name="Moderator Eli",
                password=password,
                is_staff=False,
                is_superuser=False,
            ),
            "member_zoe": self._upsert_user(
                user_model,
                username="member_zoe",
                email="zoe@spotter.local",
                display_name="Member Zoe",
                password=password,
                is_staff=False,
                is_superuser=False,
            ),
            "member_noah": self._upsert_user(
                user_model,
                username="member_noah",
                email="noah@spotter.local",
                display_name="Member Noah",
                password=password,
                is_staff=False,
                is_superuser=False,
            ),
            "new_ava": self._upsert_user(
                user_model,
                username="new_ava",
                email="ava@spotter.local",
                display_name="New User Ava",
                password=password,
                is_staff=False,
                is_superuser=False,
            ),
        }

        communities = {
            "public": self._upsert_community(
                slug="sunrise-calisthenics",
                name="Sunrise Calisthenics",
                description="Morning bodyweight sessions with beginner-friendly progressions.",
                visibility=CommunityVisibility.PUBLIC,
                created_by=users["coach_maya"],
            ),
            "private": self._upsert_community(
                slug="trail-runners-lab",
                name="Trail Runners Lab",
                description="Private conditioning group for trail athletes.",
                visibility=CommunityVisibility.PRIVATE,
                created_by=users["coach_maya"],
            ),
        }

        self._upsert_membership(
            communities["public"],
            users["coach_maya"],
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
            joined=True,
        )
        self._upsert_membership(
            communities["public"],
            users["mod_eli"],
            role=MembershipRole.MODERATOR,
            status=MembershipStatus.ACTIVE,
            joined=True,
        )
        self._upsert_membership(
            communities["public"],
            users["member_zoe"],
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            joined=True,
        )
        self._upsert_membership(
            communities["private"],
            users["coach_maya"],
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
            joined=True,
        )
        self._upsert_membership(
            communities["private"],
            users["mod_eli"],
            role=MembershipRole.MODERATOR,
            status=MembershipStatus.ACTIVE,
            joined=True,
        )

        pending_request = self._upsert_join_request(
            community=communities["private"],
            requested_by=users["new_ava"],
            status=JoinRequestStatus.PENDING,
            message="I am training for my first mountain race and want structured programming.",
        )
        self._upsert_membership(
            communities["private"],
            users["new_ava"],
            role=MembershipRole.MEMBER,
            status=MembershipStatus.PENDING,
            joined=False,
        )

        approved_request = self._upsert_join_request(
            community=communities["private"],
            requested_by=users["member_zoe"],
            status=JoinRequestStatus.APPROVED,
            message="Would love to train with this crew.",
            reviewed_by=users["mod_eli"],
            reviewed_at=timezone.now() - timedelta(days=3),
        )
        self._upsert_membership(
            communities["private"],
            users["member_zoe"],
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            joined=True,
        )

        rejected_request = self._upsert_join_request(
            community=communities["private"],
            requested_by=users["member_noah"],
            status=JoinRequestStatus.REJECTED,
            message="Looking to join immediately.",
            reviewed_by=users["mod_eli"],
            reviewed_at=timezone.now() - timedelta(days=2),
        )
        self._upsert_membership(
            communities["private"],
            users["member_noah"],
            role=MembershipRole.MEMBER,
            status=MembershipStatus.REJECTED,
            joined=False,
        )

        self._upsert_moderation_record(
            target_id=str(approved_request.id),
            decision=ModerationDecision.APPROVED,
            decided_by=users["mod_eli"],
            payload={
                "community_id": communities["private"].id,
                "request_user_id": users["member_zoe"].id,
            },
        )
        self._upsert_moderation_record(
            target_id=str(rejected_request.id),
            decision=ModerationDecision.REJECTED,
            decided_by=users["mod_eli"],
            reason="Current cohort full; invited to re-apply next month.",
            payload={
                "community_id": communities["private"].id,
                "request_user_id": users["member_noah"].id,
            },
        )

        exercises = {
            "warmup": self._upsert_exercise(
                slug="ankle-mobility-flow",
                name="Ankle Mobility Flow",
                category=ExerciseCategory.MOVEMENT_PREPARATION,
            ),
            "calisthenics": self._upsert_exercise(
                slug="split-squat-ladder",
                name="Split Squat Ladder",
                category=ExerciseCategory.CALISTHENICS,
            ),
            "regen": self._upsert_exercise(
                slug="calf-release-sequence",
                name="Calf Release Sequence",
                category=ExerciseCategory.POST_WORKOUT_REGENERATION,
            ),
        }

        plan = self._upsert_plan(
            slug="trail-base-day-a",
            name="Trail Base Day A",
            created_by=users["coach_maya"],
            community=communities["private"],
            description="Prep + strength + recovery stack for base training.",
        )
        self._upsert_plan_item(
            plan=plan,
            exercise=exercises["warmup"],
            order=1,
            duration_minutes=10,
        )
        self._upsert_plan_item(
            plan=plan,
            exercise=exercises["calisthenics"],
            order=2,
            repetitions="3x10/side",
        )
        self._upsert_plan_item(
            plan=plan,
            exercise=exercises["regen"],
            order=3,
            duration_minutes=8,
        )

        self._upsert_plan_assignment(
            plan=plan,
            assigned_to=users["member_zoe"],
            starts_on=timezone.localdate(),
            recurs_every_days=7,
        )

        self._upsert_guidance(
            title="Hydration For Long Summer Sessions",
            topic=GuidanceTopic.HYDRATION,
            author=users["coach_maya"],
            community=communities["public"],
            status=ContentStatus.APPROVED,
            body=(
                "Use pre-session hydration, in-session sodium, "
                "and post-session fluid replacement."
            ),
        )
        self._upsert_guidance(
            title="Foot Care Checklist For Trail Weeks",
            topic=GuidanceTopic.FOOT_CARE,
            author=users["member_zoe"],
            community=communities["private"],
            status=ContentStatus.PENDING,
            body="Monitor hotspots daily, rotate socks, and check toenail pressure after descents.",
        )

        self._upsert_workout_log(
            plan=plan,
            community=communities["private"],
            performed_by=users["member_zoe"],
            perceived_exertion=7,
            notes="Legs felt stable on climbs.",
            recovery_markers={"sleep_hours": 7.5, "soreness": "light"},
        )

        self._upsert_notification(
            recipient=users["mod_eli"],
            notification_type=NotificationType.JOIN_REQUEST,
            subject="New join request pending",
            body=(
                f"{users['new_ava'].display_name} requested access to "
                f"{communities['private'].name}."
            ),
            payload={
                "community_id": communities["private"].id,
                "join_request_id": pending_request.id,
            },
            delivery_status=DeliveryStatus.PENDING,
        )
        self._upsert_notification(
            recipient=users["member_noah"],
            notification_type=NotificationType.JOIN_DECISION,
            subject="Join request decision",
            body="Your request was reviewed. You can re-apply next month.",
            payload={"community_id": communities["private"].id, "decision": "rejected"},
            delivery_status=DeliveryStatus.SENT,
        )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write("Demo login password: " + password)
        self.stdout.write("Users: " + str(user_model.objects.count()))
        self.stdout.write("Communities: " + str(Community.objects.count()))
        self.stdout.write("Join requests: " + str(CommunityJoinRequest.objects.count()))
        pending_count = CommunityJoinRequest.objects.filter(
            status=JoinRequestStatus.PENDING,
        ).count()
        self.stdout.write("Pending join requests: " + str(pending_count))

    @staticmethod
    def _upsert_user(
        user_model,
        username: str,
        email: str,
        display_name: str,
        password: str,
        is_staff: bool,
        is_superuser: bool,
    ):
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "display_name": display_name,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            },
        )
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if getattr(user, "display_name", "") != display_name:
            user.display_name = display_name
            changed = True
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed = True
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed = True
        if created or not user.check_password(password):
            user.set_password(password)
            changed = True
        if changed:
            user.save()
        return user

    @staticmethod
    def _upsert_community(slug: str, name: str, description: str, visibility: str, created_by):
        community, _ = Community.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "visibility": visibility,
                "is_archived": False,
                "created_by": created_by,
            },
        )
        return community

    @staticmethod
    def _upsert_membership(community: Community, user, role: str, status: str, joined: bool):
        joined_at = timezone.now() - timedelta(days=7) if joined else None
        membership, _ = CommunityMembership.objects.update_or_create(
            community=community,
            user=user,
            defaults={
                "role": role,
                "status": status,
                "joined_at": joined_at,
            },
        )
        return membership

    @staticmethod
    def _upsert_join_request(
        community: Community,
        requested_by,
        status: str,
        message: str,
        reviewed_by=None,
        reviewed_at=None,
    ):
        join_request, _ = CommunityJoinRequest.objects.update_or_create(
            community=community,
            requested_by=requested_by,
            status=status,
            defaults={
                "message": message,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
            },
        )
        return join_request

    @staticmethod
    def _upsert_moderation_record(
        target_id: str,
        decision: str,
        decided_by,
        reason: str = "",
        payload: dict | None = None,
    ):
        ModerationRecord.objects.update_or_create(
            target_type="community_join_request",
            target_id=target_id,
            decision=decision,
            defaults={
                "reason": reason,
                "decided_by": decided_by,
                "payload": payload or {},
            },
        )

    @staticmethod
    def _upsert_exercise(slug: str, name: str, category: str):
        exercise, _ = Exercise.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "category": category,
                "description": "Demo seed exercise",
                "instructions": "Follow controlled reps and breathing.",
                "is_active": True,
            },
        )
        return exercise

    @staticmethod
    def _upsert_plan(slug: str, name: str, created_by, community: Community, description: str):
        plan, _ = WorkoutPlan.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "created_by": created_by,
                "community": community,
                "is_template": True,
                "is_published": True,
            },
        )
        return plan

    @staticmethod
    def _upsert_plan_item(
        plan: WorkoutPlan,
        exercise: Exercise,
        order: int,
        repetitions: str = "",
        duration_minutes: int | None = None,
    ):
        WorkoutPlanItem.objects.update_or_create(
            plan=plan,
            order=order,
            defaults={
                "exercise": exercise,
                "repetitions": repetitions,
                "duration_minutes": duration_minutes,
                "notes": "Seeded item",
            },
        )

    @staticmethod
    def _upsert_plan_assignment(
        plan: WorkoutPlan,
        assigned_to,
        starts_on,
        recurs_every_days: int | None = None,
    ):
        WorkoutPlanAssignment.objects.update_or_create(
            plan=plan,
            assigned_to=assigned_to,
            defaults={
                "assigned_community": None,
                "starts_on": starts_on,
                "recurs_every_days": recurs_every_days,
                "is_active": True,
            },
        )

    @staticmethod
    def _upsert_guidance(
        title: str,
        topic: str,
        author,
        community: Community,
        status: str,
        body: str,
    ):
        published_at = timezone.now() if status == ContentStatus.APPROVED else None
        GuidanceContent.objects.update_or_create(
            title=title,
            community=community,
            defaults={
                "topic": topic,
                "author": author,
                "status": status,
                "body": body,
                "published_at": published_at,
            },
        )

    @staticmethod
    def _upsert_workout_log(
        plan: WorkoutPlan,
        community: Community,
        performed_by,
        perceived_exertion: int,
        notes: str,
        recovery_markers: dict,
    ):
        WorkoutLog.objects.update_or_create(
            plan=plan,
            community=community,
            performed_by=performed_by,
            notes=notes,
            defaults={
                "perceived_exertion": perceived_exertion,
                "recovery_markers": recovery_markers,
            },
        )

    @staticmethod
    def _upsert_notification(
        recipient,
        notification_type: str,
        subject: str,
        body: str,
        payload: dict,
        delivery_status: str,
    ):
        NotificationEvent.objects.update_or_create(
            recipient=recipient,
            notification_type=notification_type,
            subject=subject,
            defaults={
                "body": body,
                "payload": payload,
                "delivery_status": delivery_status,
                "sent_at": timezone.now() if delivery_status == DeliveryStatus.SENT else None,
            },
        )
