import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.context_priority import (
    ContextPriorityReadinessError,
    verify_context_priority_readiness,
)


class Command(BaseCommand):
    help = "Verify the additive M6C-03 context-priority contract without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the privacy-safe readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_context_priority_readiness()
        except ContextPriorityReadinessError as exc:
            raise CommandError(f"Context-priority readiness verification failed: {exc}") from None

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Context-priority readiness verified ({summary.contract_version}): "
                f"{summary.projected_protocols} canonical projected protocols, "
                f"{summary.score_active_protocols} score-active; synthetic replay "
                "passed and ordinary recommendations, score state, activation, and UI "
                "remain unchanged."
            )
        )
