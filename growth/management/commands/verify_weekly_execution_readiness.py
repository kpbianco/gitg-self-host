import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.weekly_execution import (
    WeeklyExecutionReadinessError,
    verify_weekly_execution_readiness,
)


class Command(BaseCommand):
    help = "Verify the additive M6H-01 weekly execution loop without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the privacy-safe readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_weekly_execution_readiness()
        except WeeklyExecutionReadinessError as exc:
            raise CommandError(f"Weekly execution readiness verification failed: {exc}") from None

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Weekly execution readiness verified ({summary.contract_version}): "
                f"{summary.plans} plan revisions, {summary.reviews} proof reviews, "
                f"and {summary.exact_replayed_proof_events} exact proof events; "
                "evidence, scores, recommendations, and practice completion remain unchanged."
            )
        )
