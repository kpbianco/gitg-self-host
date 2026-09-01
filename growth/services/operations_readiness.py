from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder

from growth.services.data_lifecycle import (
    OWNER_ARCHIVE_SCHEMA_VERSION,
    RETENTION_POLICY_VERSION,
    build_deletion_preview,
    build_owner_archive,
    build_retention_preview,
)

OPERATIONS_READINESS_CONTRACT_VERSION = "GG-M6H-OPERATIONS-READINESS-1.0"


class OperationsReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class OperationsReadinessSummary:
    contract_version: str
    owner_archive_schema_version: str
    retention_policy_version: str
    owners: int
    owner_records: int
    archive_set_sha256: str
    retention_enabled: bool
    retention_candidates: int
    software_ready: bool
    changes_evidence: bool
    changes_score_state: bool
    changes_recommendation_order: bool
    changes_practice_completion: bool
    requires_human_gate: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def verify_operations_readiness() -> OperationsReadinessSummary:
    users = list(get_user_model().objects.order_by("pk"))
    archive_hashes: list[str] = []
    owner_records = 0
    retention_candidates = 0
    retention_enabled = settings.OWNER_RETENTION_ENABLED

    for user in users:
        first = build_owner_archive(user)
        second = build_owner_archive(user)
        if first != second:
            raise OperationsReadinessError("An owner archive was not deterministic.")
        if first.get("schema_version") != OWNER_ARCHIVE_SCHEMA_VERSION:
            raise OperationsReadinessError("An owner archive schema version is invalid.")
        privacy = first.get("privacy")
        if not isinstance(privacy, dict) or privacy.get("safe_for_sharing") is not False:
            raise OperationsReadinessError("An owner archive privacy declaration is invalid.")
        serialized = json.dumps(first, cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True)
        if user.password and user.password in serialized:
            raise OperationsReadinessError("An owner archive contains a password hash.")

        deletion = build_deletion_preview(user)
        if deletion.total_records != sum(deletion.record_counts.values()):
            raise OperationsReadinessError("An account-deletion preview count is invalid.")
        retention = build_retention_preview(user)
        if retention.total_records != sum(retention.record_counts.values()):
            raise OperationsReadinessError("A retention preview count is invalid.")
        if retention_enabled != retention.enabled:
            raise OperationsReadinessError("Retention policy state changed during verification.")
        retention_enabled = retention.enabled
        owner_records += deletion.total_records
        retention_candidates += retention.total_records
        archive_hashes.append(first["content_sha256"])

    return OperationsReadinessSummary(
        contract_version=OPERATIONS_READINESS_CONTRACT_VERSION,
        owner_archive_schema_version=OWNER_ARCHIVE_SCHEMA_VERSION,
        retention_policy_version=RETENTION_POLICY_VERSION,
        owners=len(users),
        owner_records=owner_records,
        archive_set_sha256=_canonical_hash(archive_hashes),
        retention_enabled=retention_enabled,
        retention_candidates=retention_candidates,
        software_ready=True,
        changes_evidence=False,
        changes_score_state=False,
        changes_recommendation_order=False,
        changes_practice_completion=False,
        requires_human_gate=True,
    )
