import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.m6d_authoring_readiness import (
    M6DAuthoringReadinessError,
    verify_m6d_authoring_readiness,
)


class Command(BaseCommand):
    help = (
        "Verify the exact source-only M6D-01 authoring cohort while preserving "
        "the reviewed runtime and reporting current M6B governance."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_m6d_authoring_readiness()
        except (M6DAuthoringReadinessError, ValueError) as exc:
            raise CommandError(f"M6D-01 authoring readiness verification failed: {exc}") from exc

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"M6D-01 source-only authoring readiness verified "
                f"({summary.contract_version}): {summary.source_protocol_packages} source "
                f"packages/{summary.source_practice_actions} source actions, "
                f"{summary.runtime_protocols} runtime protocols/{summary.runtime_actions} "
                f"runtime actions, {summary.typed_production_protocols} typed production "
                f"protocols, and {summary.score_active_protocols} score-active "
                f"protocol{'s' if summary.score_active_protocols != 1 else ''}. "
                f"ER-M6A-003 is {summary.expert_review_status} and RG-M6A-002 is "
                f"{summary.research_gap_status}."
            )
        )
