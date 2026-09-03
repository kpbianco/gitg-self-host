from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from growth.services.assessment_calibration import (
    AssessmentCalibrationError,
    render_assessment_calibration_export,
)


class Command(BaseCommand):
    help = "Write the explicitly consented sensitive assessment calibration dataset."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, type=Path)
        parser.add_argument(
            "--confirm-sensitive-export",
            action="store_true",
            help="Acknowledge that the output contains sensitive pseudonymous assessment data.",
        )

    def handle(self, *args, **options):
        if not options["confirm_sensitive_export"]:
            raise CommandError(
                "Refusing export without --confirm-sensitive-export. "
                "Review consent and storage first."
            )
        output = options["output"].expanduser().resolve()
        if not output.parent.is_dir():
            raise CommandError("The export output directory does not exist.")
        try:
            content = render_assessment_calibration_export()
        except AssessmentCalibrationError as exc:
            raise CommandError(f"Assessment calibration export stopped: {exc}") from None
        try:
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise CommandError("Refusing to overwrite an existing calibration export.") from None
        except OSError as exc:
            raise CommandError(f"The calibration export could not be created: {exc}") from None
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        self.stdout.write(
            self.style.SUCCESS(
                f"Sensitive assessment calibration dataset written to {output} with mode 0600."
            )
        )
