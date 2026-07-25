from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser if none exists. Intended for non-interactive deploy steps."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("DJANGO_SUPERUSER_USERNAME"),
            help="Superuser username (or set DJANGO_SUPERUSER_USERNAME)",
        )
        parser.add_argument(
            "--email",
            default=os.environ.get("DJANGO_SUPERUSER_EMAIL"),
            help="Superuser email (or set DJANGO_SUPERUSER_EMAIL)",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DJANGO_SUPERUSER_PASSWORD"),
            help="Superuser password (or set DJANGO_SUPERUSER_PASSWORD)",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()

        if user_model.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING("Superuser already exists. Skipping."))
            return

        username = (options.get("username") or "").strip()
        email = (options.get("email") or "").strip()
        password = options.get("password") or ""

        missing = []
        if not username:
            missing.append("username")
        if not email:
            missing.append("email")
        if not password:
            missing.append("password")
        if missing:
            missing_list = ", ".join(missing)
            raise CommandError(
                "Missing required values for ensure_superuser: "
                f"{missing_list}. Set DJANGO_SUPERUSER_USERNAME, "
                "DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD or pass flags."
            )

        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)

        if hasattr(user, "display_name") and not user.display_name:
            user.display_name = username

        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Promoted existing user '{username}' to superuser."
                )
            )
