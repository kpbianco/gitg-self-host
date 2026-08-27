import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.pilot_readiness import (
    PilotReadinessError,
    verify_pilot_readiness,
)


class Command(BaseCommand):
    help = "Verify the current canonical runtime and Pilot 002 boundary without writing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the readiness summary as deterministic JSON.",
        )

    def handle(self, *args, **options):
        try:
            summary = verify_pilot_readiness()
        except PilotReadinessError as exc:
            raise CommandError(f"Pilot readiness verification failed: {exc}") from exc

        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Pilot readiness verified ({summary.contract_version}): "
                f"{summary.domains} domains, {summary.competencies} competencies, "
                f"{summary.levers} levers, {summary.archetypes} archetypes, "
                f"{summary.archetype_lever_affinities} archetype affinities, "
                f"{summary.competency_lever_links} weighted links; "
                f"{summary.practice_protocols} active protocols with "
                f"{summary.practice_actions} actions and "
                f"{summary.score_active_protocols} score-active protocols; "
                f"{summary.pilot_assessment_runs} Pilot 002 profile; "
                f"{summary.evidence_events} evidence events and "
                f"{summary.score_state_runs} score-state runs replayed."
            )
        )
