import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.m6c_pilot_readiness import (
    M6CPilotReadinessError,
    verify_m6c_pilot_readiness,
)


class Command(BaseCommand):
    help = "Verify the additive M6C browser and pilot-readiness slice without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the privacy-safe readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_m6c_pilot_readiness()
        except M6CPilotReadinessError as exc:
            raise CommandError(f"M6C pilot readiness verification failed: {exc}") from None

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"M6C pilot readiness verified ({summary.contract_version}): "
                f"{len(summary.prerequisite_contract_versions)} prerequisite contracts, "
                f"{len(summary.baseline_protocol_ids)} baseline protocols, "
                f"{len(summary.authenticated_route_names)} authenticated browser routes, "
                f"{summary.personal_os_records} Personal OS revisions, "
                f"{summary.assessment_context_records} assessment-context revisions, and "
                f"{summary.practice_context_records} practice-context revisions. "
                "This is software readiness only; it does not approve release or deployment."
            )
        )
