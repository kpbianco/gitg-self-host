from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from growth.services.assessment_calibration_analysis import (
    MAX_DATASET_BYTES,
    AssessmentCalibrationAnalysisError,
    render_assessment_calibration_analysis,
)


def _reject_duplicate_object_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise AssessmentCalibrationAnalysisError(
                f"The calibration input contains a duplicate object key: {key}."
            )
        value[key] = item
    return value


class Command(BaseCommand):
    help = "Validate a sensitive calibration export and write a private aggregate analysis."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)
        parser.add_argument(
            "--confirm-sensitive-input",
            action="store_true",
            help="Acknowledge that the input contains sensitive pseudonymous assessment data.",
        )

    def handle(self, *args, **options):
        if not options["confirm_sensitive_input"]:
            raise CommandError(
                "Refusing analysis without --confirm-sensitive-input. "
                "Review consent and private storage first."
            )
        input_path = Path(options["input"]).expanduser().resolve()
        output_path = Path(options["output"]).expanduser().resolve()
        if input_path == output_path:
            raise CommandError("The calibration input and analysis output must be different files.")
        if not input_path.is_file():
            raise CommandError("The calibration input file does not exist.")
        if input_path.stat().st_size > MAX_DATASET_BYTES:
            raise CommandError("The calibration input exceeds the supported size limit.")
        if not output_path.parent.is_dir():
            raise CommandError("The analysis output directory does not exist.")
        try:
            dataset = json.loads(
                input_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_object_keys,
            )
            content = render_assessment_calibration_analysis(dataset)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"The calibration input could not be read: {exc}") from None
        except AssessmentCalibrationAnalysisError as exc:
            raise CommandError(f"Assessment calibration analysis stopped: {exc}") from None
        try:
            descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise CommandError("Refusing to overwrite an existing calibration analysis.") from None
        except OSError as exc:
            raise CommandError(f"The calibration analysis could not be created: {exc}") from None
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
        except Exception:
            output_path.unlink(missing_ok=True)
            raise
        self.stdout.write(
            self.style.SUCCESS(
                f"Sensitive aggregate calibration analysis written to {output_path} "
                "with mode 0600; zero evidence axes completed."
            )
        )
