from django.core.management.base import BaseCommand, CommandError

from growth.services.canonical_import import CanonicalDataError, seed_canonical_data


class Command(BaseCommand):
    help = "Validate and idempotently seed canonical curriculum, model, and Pilot 002 data."

    def handle(self, *args, **options):
        try:
            summary = seed_canonical_data()
        except CanonicalDataError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "Canonical seed complete: "
                f"{summary.levers} levers, "
                f"{summary.competencies} competencies, "
                f"{summary.competency_lever_links} weighted links, "
                f"{summary.practice_protocols} practice protocols, "
                f"{summary.pilot_lever_baselines} Pilot 002 baselines."
            )
        )
