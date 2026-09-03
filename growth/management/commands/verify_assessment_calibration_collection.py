import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.assessment_calibration import (
    AssessmentCalibrationError,
    verify_assessment_calibration_collection_readiness,
)


class Command(BaseCommand):
    help = "Verify opt-in assessment calibration collection without changing state."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        try:
            summary = verify_assessment_calibration_collection_readiness()
        except AssessmentCalibrationError as exc:
            raise CommandError(
                f"Assessment calibration collection verification failed: {exc}"
            ) from None
        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Assessment calibration collection verified ({summary.contract_version}): "
                f"{summary.active_participants} active participant(s), "
                f"{summary.active_assessment_runs} included assessment(s); "
                "zero participant evidence axes completed."
            )
        )
