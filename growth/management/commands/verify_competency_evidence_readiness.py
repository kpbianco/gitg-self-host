import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.competency_evidence_readiness import (
    CompetencyEvidenceReadinessError,
    verify_competency_evidence_readiness,
)


class Command(BaseCommand):
    help = (
        "Verify additive M6B software readiness while retaining specialist "
        "acceptance as a separate gate."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_competency_evidence_readiness()
        except (CompetencyEvidenceReadinessError, ValueError) as exc:
            raise CommandError(f"Competency-evidence readiness verification failed: {exc}") from exc

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Competency-evidence software readiness verified "
                f"({summary.contract_version}): "
                f"{summary.canonical_protocol_packages} canonical packages, "
                f"{summary.practice_actions} actions, "
                f"{summary.uncovered_competencies} explicitly unauthored "
                "competencies, 0 typed production protocols, and 0 typed "
                "score-active protocols. ER-M6A-003 remains pending and "
                "RG-M6A-002 remains open, so M6B is not accepted."
            )
        )
