from django.core.management.base import BaseCommand, CommandError

from growth.services.practice_content_reports import (
    PracticeReportError,
    write_or_check_practice_reports,
)


class Command(BaseCommand):
    help = "Generate or verify deterministic M6 practice-content reports."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Fail when committed reports are missing or stale.",
        )

    def handle(self, *args, **options):
        check = options["check"]
        try:
            changed = write_or_check_practice_reports(check=check)
        except (PracticeReportError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        if check:
            self.stdout.write(self.style.SUCCESS("Practice-content reports are current."))
        elif changed:
            self.stdout.write(
                self.style.SUCCESS(
                    "Generated practice-content reports: "
                    + ", ".join(path.as_posix() for path in changed)
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Practice-content reports were already current."))
