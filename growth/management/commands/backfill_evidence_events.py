from django.core.management.base import BaseCommand, CommandError

from growth.services.evidence import EvidenceWorkflowError, backfill_evidence_events


class Command(BaseCommand):
    help = (
        "Create immutable GG-EVIDENCE-1.0 events for submitted M1 check-ins "
        "that do not already have one."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report missing events without writing them.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        try:
            summary = backfill_evidence_events(dry_run=dry_run)
        except EvidenceWorkflowError as exc:
            raise CommandError(str(exc)) from exc

        missing = (
            summary.submitted_check_ins - summary.events_already_present - summary.events_created
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Evidence backfill dry run: {summary.submitted_check_ins} submitted, "
                    f"{summary.events_already_present} already present, {missing} would be created."
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Evidence backfill complete: {summary.submitted_check_ins} submitted, "
                f"{summary.events_created} created, "
                f"{summary.events_already_present} already present."
            )
        )
