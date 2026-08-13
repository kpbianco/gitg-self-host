import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.context import ContextReadinessError, verify_context_readiness


class Command(BaseCommand):
    help = "Verify the additive M6C-01 context foundation without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_context_readiness()
        except ContextReadinessError as exc:
            raise CommandError(f"Context readiness verification failed: {exc}") from exc

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Context readiness verified ({summary.contract_version}): "
                f"{summary.assessment_records} assessment-context revisions and "
                f"{summary.practice_records} practice-context revisions; "
                "recommendations, score state, and ordinary UI remain unchanged."
            )
        )
