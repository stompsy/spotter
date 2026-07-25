from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import DeliveryStatus, NotificationEvent, NotificationType
from apps.workouts.models import WorkoutPlanAssignment


class Command(BaseCommand):
    help = "Dispatch reminder notifications for due workout assignments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=0,
            help="Include assignments due up to N days ahead (default: 0).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print candidates without creating notifications.",
        )

    def handle(self, *args, **options):
        days_ahead = max(options["days_ahead"], 0)
        dry_run = options["dry_run"]

        today = timezone.localdate()
        due_by = today + timedelta(days=days_ahead)
        candidates = self._candidate_assignments(today=today, due_by=due_by)

        created_count = 0
        for assignment in candidates:
            recipient = assignment.assigned_to
            if recipient is None:
                continue

            subject = f"Workout reminder: {assignment.plan.name}"
            body = self._build_body(assignment=assignment, today=today)
            payload = {
                "assignment_id": assignment.id,
                "plan_id": assignment.plan_id,
                "starts_on": assignment.starts_on.isoformat() if assignment.starts_on else None,
                "recurs_every_days": assignment.recurs_every_days,
            }

            if dry_run:
                dry_run_line = (
                    f"[dry-run] user={recipient.username} "
                    f"assignment={assignment.id} "
                    f"plan={assignment.plan.name}"
                )
                self.stdout.write(
                    dry_run_line
                )
                continue

            duplicate_exists = NotificationEvent.objects.filter(
                recipient=recipient,
                notification_type=NotificationType.REMINDER,
                payload__assignment_id=assignment.id,
                created_at__date=today,
            ).exists()
            if duplicate_exists:
                continue

            NotificationEvent.objects.create(
                recipient=recipient,
                notification_type=NotificationType.REMINDER,
                subject=subject,
                body=body,
                payload=payload,
                delivery_status=DeliveryStatus.PENDING,
            )
            created_count += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete."))
            return

        self.stdout.write(self.style.SUCCESS(f"Created {created_count} reminder notification(s)."))

    @staticmethod
    def _candidate_assignments(today, due_by):
        return (
            WorkoutPlanAssignment.objects.select_related("plan", "assigned_to")
            .filter(
                assigned_to__isnull=False,
                is_active=True,
                ended_at__isnull=True,
            )
            .filter(Q(starts_on__isnull=True) | Q(starts_on__lte=due_by))
            .order_by("id")
        )

    @staticmethod
    def _build_body(assignment: WorkoutPlanAssignment, today):
        if assignment.starts_on:
            if assignment.starts_on <= today:
                timing = "starting now"
            else:
                timing = f"starting on {assignment.starts_on.isoformat()}"
        else:
            timing = "available now"

        recurrence = (
            f" Recurs every {assignment.recurs_every_days} day(s)."
            if assignment.recurs_every_days
            else ""
        )
        return f"Your assigned workout plan '{assignment.plan.name}' is {timing}.{recurrence}"
