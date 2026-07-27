from django.core.management.base import BaseCommand, CommandError

from growth.services.evidence import EvidenceWorkflowError, verify_all_evidence_events


class Command(BaseCommand):
    help = "Replay every evidence event and verify complete submission coverage without writing."

    def handle(self, *args, **options):
        try:
            summary = verify_all_evidence_events()
        except EvidenceWorkflowError as exc:
            raise CommandError(f"Evidence verification failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Evidence verification passed: "
                f"{summary.events_verified} events replayed for "
                f"{summary.submitted_check_ins} submitted check-ins."
            )
        )
