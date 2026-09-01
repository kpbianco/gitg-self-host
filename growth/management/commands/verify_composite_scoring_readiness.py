import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.composite_scoring_readiness import (
    CompositeScoringReadinessError,
    verify_composite_scoring_readiness,
)


class Command(BaseCommand):
    help = "Verify deterministic composite assessment and human-closeout scoring readiness."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Print the summary as JSON.")

    def handle(self, *args, **options):
        try:
            summary = verify_composite_scoring_readiness()
        except CompositeScoringReadinessError as exc:
            raise CommandError(f"Composite scoring readiness failed: {exc}") from exc
        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return
        self.stdout.write(
            self.style.SUCCESS(
                "Composite scoring readiness passed: "
                f"{summary.competencies_per_epoch} competencies, "
                f"{summary.practices} practices, {summary.actions} actions; "
                "specialist review remains pending."
            )
        )
