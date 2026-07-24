import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the one-time bootstrap user when the database has no users."

    def handle(self, *args, **options):
        user_model = get_user_model()
        if user_model.objects.exists():
            self.stdout.write("Bootstrap skipped: an application user already exists.")
            return

        username = os.getenv("APP_BOOTSTRAP_USERNAME", "").strip()
        password = os.getenv("APP_BOOTSTRAP_PASSWORD", "")
        if not username or not password:
            raise CommandError(
                "APP_BOOTSTRAP_USERNAME and APP_BOOTSTRAP_PASSWORD are required "
                "when no application user exists."
            )

        candidate = user_model(username=username)
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError("Bootstrap password rejected: " + "; ".join(exc.messages)) from exc

        user_model.objects.create_user(username=username, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created bootstrap user {username!r}."))
