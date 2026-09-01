import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.operations_readiness import (
    OperationsReadinessError,
    verify_operations_readiness,
)


class Command(BaseCommand):
    help = "Verify M6H-02 owner data-lifecycle operations without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the privacy-safe readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_operations_readiness()
        except OperationsReadinessError as exc:
            raise CommandError(f"M6H-02 operations readiness verification failed: {exc}") from None
        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"M6H-02 operations readiness verified ({summary.contract_version}): "
                f"{summary.owners} owner(s), {summary.owner_records} owner record(s), "
                f"retention enabled={str(summary.retention_enabled).lower()}; "
                "evidence, scores, recommendations, and completion remain unchanged."
            )
        )
