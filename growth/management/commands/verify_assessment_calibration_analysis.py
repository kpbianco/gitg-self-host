import json

from django.core.management.base import BaseCommand, CommandError

from growth.services.assessment_calibration_analysis import (
    AssessmentCalibrationAnalysisError,
    verify_assessment_calibration_analysis_readiness,
)


class Command(BaseCommand):
    help = (
        "Verify private aggregate calibration analysis readiness without reading participant data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        try:
            summary = verify_assessment_calibration_analysis_readiness()
        except AssessmentCalibrationAnalysisError as exc:
            raise CommandError(
                f"Assessment calibration analysis verification failed: {exc}"
            ) from None
        if options["json"]:
            self.stdout.write(json.dumps(summary.as_dict(), sort_keys=True))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Assessment calibration analysis readiness verified "
                f"({summary.contract_version}) with {summary.synthetic_participants} "
                "synthetic participants and zero completed evidence axes."
            )
        )
