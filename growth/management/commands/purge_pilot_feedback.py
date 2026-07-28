from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from growth.models import PilotFeedback


class Command(BaseCommand):
    help = (
        "Preview or permanently delete one participant's optional pilot-feedback "
        "records without changing developmental state."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help="Exact local username whose optional pilot feedback should be targeted.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Perform the deletion. Without this flag the command is read-only.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("The local user was not found.") from exc

        records = PilotFeedback.objects.filter(user=user)
        count = records.count()
        if not options["confirm"]:
            self.stdout.write(
                f"Dry run: {count} optional pilot-feedback record(s) would be deleted "
                f"for {username}. Re-run with --confirm to delete them."
            )
            return

        records.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} optional pilot-feedback record(s) for {username}. "
                "Assessment, evidence, score, practice, and review state were unchanged. "
                "Existing backups may still contain the deleted records."
            )
        )
