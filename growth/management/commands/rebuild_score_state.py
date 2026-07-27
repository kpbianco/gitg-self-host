from django.core.management.base import BaseCommand, CommandError

from growth.models import EvidenceEvent
from growth.services.score_state import (
    ScoreStateError,
    reverse_evidence_event,
    synchronize_all_score_states,
    verify_all_score_states,
)


class Command(BaseCommand):
    help = (
        "Initialize, process, rebuild, or verify versioned current score state "
        "from immutable assessment baselines and evidence events."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify-only",
            action="store_true",
            help="Verify all score states without writing.",
        )
        parser.add_argument(
            "--reverse-event",
            metavar="UUID",
            help="Permanently exclude one processed evidence event from current score state.",
        )
        parser.add_argument(
            "--reason",
            help="Required audit reason when --reverse-event is used.",
        )

    def handle(self, *args, **options):
        verify_only = options["verify_only"]
        event_id = options["reverse_event"]
        reason = options["reason"] or ""
        if verify_only and event_id:
            raise CommandError("--verify-only and --reverse-event cannot be combined.")
        if reason and not event_id:
            raise CommandError("--reason is only valid with --reverse-event.")

        try:
            if event_id:
                if not reason.strip():
                    raise CommandError("--reason is required with --reverse-event.")
                try:
                    event = EvidenceEvent.objects.get(pk=event_id)
                except (EvidenceEvent.DoesNotExist, ValueError) as exc:
                    raise CommandError("The evidence event was not found.") from exc
                snapshot = reverse_evidence_event(event, reason=reason)
                self.stdout.write(
                    self.style.SUCCESS(f"Score event reversal recorded as snapshot {snapshot.pk}.")
                )
                return

            if verify_only:
                summary = verify_all_score_states()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Score-state verification passed for "
                        f"{summary.assessment_runs} assessment runs."
                    )
                )
                return

            summary = synchronize_all_score_states()
        except ScoreStateError as exc:
            raise CommandError(f"Score-state operation failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Score-state rebuild complete: "
                f"{summary.assessment_runs} assessment runs, "
                f"{summary.states_initialized} initialized, "
                f"{summary.events_processed} events processed, "
                f"{summary.rebuilds_created} repairs."
            )
        )
