from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the Exercise Reviewers group and assign review permissions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--usernames",
            nargs="*",
            default=[],
            help="Optional usernames to add to the Exercise Reviewers group",
        )

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name="Exercise Reviewers")
        permission = Permission.objects.get(codename="review_exercisecandidate")
        group.permissions.add(permission)

        action_text = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action_text} group '{group.name}' with permission '{permission.codename}'"
            )
        )

        usernames = options["usernames"]
        if not usernames:
            return

        user_model = get_user_model()
        users = list(user_model.objects.filter(username__in=usernames))
        found_usernames = {user.username for user in users}
        missing = sorted(set(usernames) - found_usernames)
        if missing:
            missing_text = ", ".join(missing)
            raise CommandError(f"Unknown usernames: {missing_text}")

        for user in users:
            group.user_set.add(user)

        self.stdout.write(self.style.SUCCESS(f"Added {len(users)} users to '{group.name}'"))
