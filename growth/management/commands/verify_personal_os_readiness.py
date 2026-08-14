import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.personal_os import (
    PersonalOSReadinessError,
    verify_personal_os_readiness,
)


class Command(BaseCommand):
    help = "Verify the additive M6C-02 Personal OS foundation without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the privacy-safe readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_personal_os_readiness()
        except PersonalOSReadinessError as exc:
            raise CommandError(f"Personal OS readiness verification failed: {exc}") from None

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Personal OS readiness verified ({summary.contract_version}): "
                f"{summary.records} private revisions across "
                f"{summary.assessment_epochs_with_personal_os} assessment epochs; "
                "recommendations, score state, activation, and ordinary UI remain unchanged."
            )
        )
