import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.expansion_readiness import (
    ExpansionReadinessError,
    verify_expansion_readiness,
)


class Command(BaseCommand):
    help = "Verify the additive M6A curriculum-expansion foundation without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_expansion_readiness()
        except ExpansionReadinessError as exc:
            raise CommandError(
                f"Curriculum expansion readiness verification failed: {exc}"
            ) from exc

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Expansion readiness verified ({summary.contract_version}): "
                f"{summary.canonical_protocol_packages} canonical packages and "
                f"{summary.practice_actions} actions project "
                f"{summary.runtime_protocols} runtime protocols; "
                f"{summary.uncovered_competencies} of {summary.competencies} "
                "competencies remain explicitly unauthored; "
                f"{summary.score_active_protocols} score-active protocols; "
                f"{summary.projected_legacy_protocols} legacy-compatible projections; "
                f"legacy projection hash {summary.legacy_projection_hash}."
            )
        )
