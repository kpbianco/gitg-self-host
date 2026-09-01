from django.core.management.base import BaseCommand, CommandError

from growth.models import CompletionCreditEvent
from growth.services.composite_score_state import (
    CompositeScoreStateError,
    reverse_completion_credit_event,
    synchronize_all_composite_score_states,
    verify_all_composite_score_states,
)


class Command(BaseCommand):
    help = (
        "Initialize, replay, repair, or verify composite completion-credit state "
        "from immutable assessment projections and human closeout events."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify-only",
            action="store_true",
            help="Verify every composite score state without writing.",
        )
        parser.add_argument(
            "--reverse-event",
            metavar="UUID",
            help="Exclude one processed completion-credit closeout from current state.",
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
                    event = CompletionCreditEvent.objects.get(pk=event_id)
                except (CompletionCreditEvent.DoesNotExist, ValueError) as exc:
                    raise CommandError("The completion-credit event was not found.") from exc
                snapshot = reverse_completion_credit_event(event, reason=reason)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Completion-credit reversal recorded as snapshot {snapshot.pk}."
                    )
                )
                return

            if verify_only:
                summary = verify_all_composite_score_states()
                self.stdout.write(
                    self.style.SUCCESS(
                        "Composite score-state verification passed for "
                        f"{summary.assessment_runs} assessment runs."
                    )
                )
                return

            summary = synchronize_all_composite_score_states()
        except CompositeScoreStateError as exc:
            raise CommandError(f"Composite score-state operation failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Composite score-state rebuild complete: "
                f"{summary.assessment_runs} assessment runs, "
                f"{summary.states_initialized} initialized, "
                f"{summary.events_processed} closeouts processed, "
                f"{summary.rebuilds_created} repairs."
            )
        )
