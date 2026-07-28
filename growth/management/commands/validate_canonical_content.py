from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from growth.domain.practice_content import PracticeContentError, load_practice_content_bundle
from growth.domain.typed_evidence import (
    TypedEvidenceContractError,
    load_typed_evidence_spec,
)
from growth.services.canonical_import import (
    CanonicalDataError,
    load_and_validate_bundle,
    validate_practice_content_mapping,
)


class Command(BaseCommand):
    help = (
        "Validate canonical model, practice content, and typed evidence "
        "without writing database state."
    )

    def handle(self, *args, **options):
        try:
            canonical = load_and_validate_bundle()
            practices = load_practice_content_bundle(Path(settings.BASE_DIR))
            validate_practice_content_mapping(practices, canonical)
            typed_spec = load_typed_evidence_spec(Path(settings.BASE_DIR) / "data" / "evidence")
        except (
            CanonicalDataError,
            PracticeContentError,
            TypedEvidenceContractError,
        ) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "Canonical content valid: "
                f"{len(practices.protocols)} practice packages, "
                f"content hash {practices.content_hash}, "
                f"runtime projection "
                f"{practices.release_manifest['legacy_projection_hash']}; "
                f"typed evidence {typed_spec.algorithm_version}."
            )
        )
