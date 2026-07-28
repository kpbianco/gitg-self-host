from django.core.management.base import BaseCommand, CommandError

from growth.services.competency_evidence_reports import (
    CompetencyEvidenceReportError,
    write_or_check_competency_evidence_reports,
)


class Command(BaseCommand):
    help = "Generate or verify deterministic M6B competency-evidence reports."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Fail when committed reports are missing or stale.",
        )

    def handle(self, *args, **options):
        check = options["check"]
        try:
            changed = write_or_check_competency_evidence_reports(check=check)
        except (CompetencyEvidenceReportError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        if check:
            self.stdout.write(self.style.SUCCESS("Competency-evidence reports are current."))
        elif changed:
            self.stdout.write(
                self.style.SUCCESS(
                    "Generated competency-evidence reports: "
                    + ", ".join(path.as_posix() for path in changed)
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Competency-evidence reports were already current.")
            )
