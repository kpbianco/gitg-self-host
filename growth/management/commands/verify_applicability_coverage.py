import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.applicability_coverage import (
    ApplicabilityCoverageError,
    verify_applicability_coverage_readiness,
)


class Command(BaseCommand):
    help = "Verify personal-applicable coverage without writing score state."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        try:
            summary = verify_applicability_coverage_readiness()
        except ApplicabilityCoverageError as exc:
            raise CommandError(f"Applicability coverage verification failed: {exc}") from None
        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Applicability coverage verified ({summary.contract_version}): "
                f"{summary.assessment_epochs} assessment epoch(s), "
                f"{summary.canonical_competencies} canonical competencies; "
                "canonical score state unchanged."
            )
        )
