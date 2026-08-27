import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.competency_evidence_readiness import (
    CompetencyEvidenceReadinessError,
    verify_competency_evidence_readiness,
)


class Command(BaseCommand):
    help = (
        "Verify all-catalog competency evidence readiness while retaining "
        "specialist acceptance as a separate audit."
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
                f"competencies, {summary.typed_production_protocols} typed "
                f"production protocols, {summary.typed_score_active_protocols} "
                f"typed score-active protocols, and "
                f"{summary.score_active_protocols} total score-active protocols. "
                "Owner-directed M6F software activation is effective; the "
                f"separate M6B specialist audit remains tracked as "
                f"{summary.expert_review_id}={summary.expert_review_status} and "
                f"{summary.research_gap_id}={summary.research_gap_status}."
            )
        )
