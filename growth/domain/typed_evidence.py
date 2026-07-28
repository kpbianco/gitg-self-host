from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

TYPED_EVIDENCE_ALGORITHM_VERSION = "GG-TYPED-EVIDENCE-1.0"
TYPED_EVIDENCE_RULES_VERSION = "typed-evidence-rules-v1"
TYPED_EVIDENCE_SPEC_VERSION = "GG-TYPED-EVIDENCE-SPEC-1.0"
TYPED_EVIDENCE_RELEASE_VERSION = "GG-TYPED-EVIDENCE-RELEASE-1.0"

FOUR_PLACES = Decimal("0.0001")
STABLE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SUPPORTED_SCORING_POLICY_IDS = frozenset(
    {
        "SP-SELF-REPORT-ELIGIBLE",
        "SP-CORROBORATION-REQUIRED",
        "SP-ARTIFACT-OBJECTIVE-PREFERRED",
        "SP-QUALIFIED-EVIDENCE-REQUIRED",
        "SP-SHADOW-ONLY",
        "SP-NON-SCORED-REFLECTION",
    }
)


class TypedEvidenceContractError(ValueError):
    pass


@dataclass(frozen=True)
class TypedEvidenceSpec:
    schema_version: str
    algorithm_version: str
    rules_schema_version: str
    measurement_kinds: tuple[str, ...]
    observation_states: tuple[str, ...]
    provenance_kinds: tuple[str, ...]
    evidence_directions: tuple[str, ...]
    support_factors: tuple[tuple[str, Decimal], ...]
    context_factors: tuple[tuple[str, Decimal], ...]
    repetition_multipliers: tuple[Decimal, ...]
    performance_attempt_weight: Decimal
    performance_completion_weight: Decimal
    performance_primary_weight: Decimal
    performance_supporting_weight: Decimal
    quality_base: Decimal
    quality_attempt_bonus: Decimal
    quality_direction_bonus: Decimal
    quality_support_bonus: Decimal
    quality_context_bonus: Decimal
    quality_observed_bonus: Decimal
    quality_cap: Decimal

    @property
    def support_factor_map(self) -> dict[str, Decimal]:
        return dict(self.support_factors)

    @property
    def context_factor_map(self) -> dict[str, Decimal]:
        return dict(self.context_factors)

    def materialized(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm_version": self.algorithm_version,
            "rules_schema_version": self.rules_schema_version,
            "measurement_kinds": list(self.measurement_kinds),
            "observation_states": list(self.observation_states),
            "provenance_kinds": list(self.provenance_kinds),
            "evidence_directions": list(self.evidence_directions),
            "support_factors": {key: _decimal_string(value) for key, value in self.support_factors},
            "context_factors": {key: _decimal_string(value) for key, value in self.context_factors},
            "repetition_multipliers": [
                _decimal_string(value) for value in self.repetition_multipliers
            ],
            "performance_weights": {
                "attempt": _decimal_string(self.performance_attempt_weight),
                "completion": _decimal_string(self.performance_completion_weight),
                "primary": _decimal_string(self.performance_primary_weight),
                "supporting": _decimal_string(self.performance_supporting_weight),
            },
            "quality_weights": {
                "base": _decimal_string(self.quality_base),
                "attempt_bonus": _decimal_string(self.quality_attempt_bonus),
                "direction_bonus": _decimal_string(self.quality_direction_bonus),
                "support_bonus": _decimal_string(self.quality_support_bonus),
                "context_bonus": _decimal_string(self.quality_context_bonus),
                "observed_bonus": _decimal_string(self.quality_observed_bonus),
                "cap": _decimal_string(self.quality_cap),
            },
        }


@dataclass(frozen=True)
class TypedObservationInput:
    measurement_id: str
    kind: str
    state: str
    provenance_kind: str
    value: Any = None


@dataclass(frozen=True)
class TypedEvidenceInput:
    event_key: str
    origin_key: str
    assessment_epoch_id: str
    protocol_stable_id: str
    action_stable_id: str
    competency_stable_id: str
    scoring_policy_id: str
    action_attempted: bool
    action_completed: bool
    observations: tuple[TypedObservationInput, ...]
    support_level: str
    context_comparison: str
    context_key: str
    evidence_direction: str
    adverse_indicator_ids: tuple[str, ...]
    repetition_index: int
    observed_on: str
    as_of_date: str


@dataclass(frozen=True)
class TypedEvidenceResult:
    algorithm_version: str
    performance: Decimal
    quality: Decimal
    independence: Decimal
    context_breadth: Decimal
    repetition_index: int
    repetition_multiplier: Decimal
    contradiction_level: Decimal | None
    base_evidence_mass: Decimal
    direction: str
    adverse: bool
    recency_status: str
    provenance_kinds: tuple[str, ...]
    competency_performance: Decimal | None
    transfer_disposition: str
    withholding_reasons: tuple[str, ...]
    input_snapshot: dict[str, Any]
    explanation: dict[str, Any]


def _default_evidence_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "evidence"


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TypedEvidenceContractError(f"{path}: could not read valid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise TypedEvidenceContractError(f"{path}: expected an object.")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TypedEvidenceContractError(f"{path}: could not read valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TypedEvidenceContractError(f"{path}: expected an object.")
    return value


def _validate_schema(document: Mapping[str, Any], schema: Mapping[str, Any], path: Path) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: tuple(str(item) for item in error.absolute_path),
        )
    except SchemaError as exc:
        raise TypedEvidenceContractError(f"{path}: invalid JSON schema: {exc.message}") from exc
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "<root>"
        raise TypedEvidenceContractError(f"{path}:{location}: {error.message}")


def _canonical_content_hash(
    root: Path,
    manifest: Mapping[str, Any],
    content_paths: Sequence[Path],
) -> str:
    digest = hashlib.sha256()
    projection = {key: value for key, value in manifest.items() if key != "content_hash"}
    digest.update(b"release_manifest.yaml\0")
    digest.update(json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    digest.update(b"\0")
    for path in sorted(content_paths):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _canonical_object_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (ArithmeticError, ValueError) as exc:
        raise TypedEvidenceContractError(f"{label} must be a finite decimal.") from exc
    if not result.is_finite():
        raise TypedEvidenceContractError(f"{label} must be a finite decimal.")
    return result


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")


def _bounded_decimal(value: Any, label: str) -> Decimal:
    result = _decimal(value, label)
    if result < 0 or result > 1:
        raise TypedEvidenceContractError(f"{label} must be in [0, 1].")
    return result


def _unique_strings(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise TypedEvidenceContractError(f"{label} must be a non-empty list.")
    if any(not isinstance(item, str) or not item for item in value):
        raise TypedEvidenceContractError(f"{label} entries must be non-empty strings.")
    if len(value) != len(set(value)):
        raise TypedEvidenceContractError(f"{label} contains duplicates.")
    return tuple(value)


def _spec_from_mapping(document: Mapping[str, Any]) -> TypedEvidenceSpec:
    expected = {
        "schema_version",
        "algorithm_version",
        "rules_schema_version",
        "measurement_kinds",
        "observation_states",
        "provenance_kinds",
        "evidence_directions",
        "support_factors",
        "context_factors",
        "repetition_multipliers",
        "performance_weights",
        "quality_weights",
    }
    if set(document) != expected:
        raise TypedEvidenceContractError(
            "Typed evidence spec fields do not match the accepted contract."
        )
    if document["schema_version"] != TYPED_EVIDENCE_SPEC_VERSION:
        raise TypedEvidenceContractError("Typed evidence spec version is unsupported.")
    if document["algorithm_version"] != TYPED_EVIDENCE_ALGORITHM_VERSION:
        raise TypedEvidenceContractError("Typed evidence algorithm version is unsupported.")
    if document["rules_schema_version"] != TYPED_EVIDENCE_RULES_VERSION:
        raise TypedEvidenceContractError("Typed evidence rules version is unsupported.")

    measurement_kinds = _unique_strings(document["measurement_kinds"], "measurement_kinds")
    required_kinds = {
        "boolean",
        "count",
        "bounded_frequency",
        "ordinal",
        "duration",
        "artifact",
        "conceptual",
        "scenario",
        "objective",
        "attestation",
    }
    if set(measurement_kinds) != required_kinds:
        raise TypedEvidenceContractError("Typed evidence measurement kinds are incomplete.")

    states = _unique_strings(document["observation_states"], "observation_states")
    if set(states) != {
        "observed",
        "unknown",
        "not_observed",
        "withheld",
        "not_applicable",
        "deferred",
    }:
        raise TypedEvidenceContractError("Typed evidence observation states are incomplete.")
    provenance = _unique_strings(document["provenance_kinds"], "provenance_kinds")
    if set(provenance) != {
        "firsthand_self_report",
        "reviewed_artifact",
        "objective_indicator",
        "consented_observer",
        "qualified_attestation",
    }:
        raise TypedEvidenceContractError("Typed evidence provenance kinds are incomplete.")
    directions = _unique_strings(document["evidence_directions"], "evidence_directions")
    if set(directions) != {"supports", "mixed", "contradicts", "inconclusive", "unknown"}:
        raise TypedEvidenceContractError("Typed evidence directions are incomplete.")

    support_raw = document["support_factors"]
    context_raw = document["context_factors"]
    if not isinstance(support_raw, Mapping) or not isinstance(context_raw, Mapping):
        raise TypedEvidenceContractError("Support and context factors must be objects.")
    if set(support_raw) != {"self_directed", "planning_aid", "guided", "not_recorded"}:
        raise TypedEvidenceContractError("Support factors are incomplete.")
    if set(context_raw) != {"first_record", "same_context", "varied_context"}:
        raise TypedEvidenceContractError("Context factors are incomplete.")
    support = tuple(
        sorted(
            (key, _bounded_decimal(value, f"support_factors.{key}"))
            for key, value in support_raw.items()
        )
    )
    context = tuple(
        sorted(
            (key, _bounded_decimal(value, f"context_factors.{key}"))
            for key, value in context_raw.items()
        )
    )

    repetitions_raw = document["repetition_multipliers"]
    if not isinstance(repetitions_raw, list) or not repetitions_raw:
        raise TypedEvidenceContractError("repetition_multipliers must be a non-empty list.")
    repetitions = tuple(
        _bounded_decimal(value, "repetition_multipliers") for value in repetitions_raw
    )
    if any(value <= 0 for value in repetitions):
        raise TypedEvidenceContractError("Repetition multipliers must be positive.")
    if any(later > earlier for earlier, later in pairwise(repetitions)):
        raise TypedEvidenceContractError("Repetition multipliers must not increase.")

    performance = document["performance_weights"]
    quality = document["quality_weights"]
    if not isinstance(performance, Mapping) or set(performance) != {
        "attempt",
        "completion",
        "primary",
        "supporting",
    }:
        raise TypedEvidenceContractError("Performance weights are malformed.")
    if not isinstance(quality, Mapping) or set(quality) != {
        "base",
        "attempt_bonus",
        "direction_bonus",
        "support_bonus",
        "context_bonus",
        "observed_bonus",
        "cap",
    }:
        raise TypedEvidenceContractError("Quality weights are malformed.")
    performance_values = {
        key: _bounded_decimal(value, f"performance_weights.{key}")
        for key, value in performance.items()
    }
    if sum(performance_values.values(), Decimal("0")) > 1:
        raise TypedEvidenceContractError("Performance weights cannot exceed one.")
    quality_values = {
        key: _bounded_decimal(value, f"quality_weights.{key}") for key, value in quality.items()
    }
    return TypedEvidenceSpec(
        schema_version=document["schema_version"],
        algorithm_version=document["algorithm_version"],
        rules_schema_version=document["rules_schema_version"],
        measurement_kinds=measurement_kinds,
        observation_states=states,
        provenance_kinds=provenance,
        evidence_directions=directions,
        support_factors=support,
        context_factors=context,
        repetition_multipliers=repetitions,
        performance_attempt_weight=performance_values["attempt"],
        performance_completion_weight=performance_values["completion"],
        performance_primary_weight=performance_values["primary"],
        performance_supporting_weight=performance_values["supporting"],
        quality_base=quality_values["base"],
        quality_attempt_bonus=quality_values["attempt_bonus"],
        quality_direction_bonus=quality_values["direction_bonus"],
        quality_support_bonus=quality_values["support_bonus"],
        quality_context_bonus=quality_values["context_bonus"],
        quality_observed_bonus=quality_values["observed_bonus"],
        quality_cap=quality_values["cap"],
    )


@lru_cache(maxsize=8)
def load_typed_evidence_spec(base_dir: Path | None = None) -> TypedEvidenceSpec:
    root = (base_dir or _default_evidence_root()).resolve()
    manifest_path = root / "release_manifest.yaml"
    manifest = _read_yaml(manifest_path)
    manifest_schema_path = root / "schema" / "release_manifest_v1.schema.json"
    manifest_schema = _read_json(manifest_schema_path)
    _validate_schema(manifest, manifest_schema, manifest_path)
    if manifest.get("schema_version") != TYPED_EVIDENCE_RELEASE_VERSION:
        raise TypedEvidenceContractError("Typed evidence release version is unsupported.")
    if manifest.get("algorithm_version") != TYPED_EVIDENCE_ALGORITHM_VERSION:
        raise TypedEvidenceContractError("Typed evidence release algorithm is unsupported.")

    raw_files = _unique_strings(manifest.get("content_files"), "release_manifest.content_files")
    paths: list[Path] = []
    for raw in raw_files:
        candidate = (root / raw).resolve()
        if root not in candidate.parents or candidate == root or not candidate.is_file():
            raise TypedEvidenceContractError(
                f"release_manifest: unsafe or missing content path {raw!r}."
            )
        paths.append(candidate)
    discovered = {
        path.resolve()
        for path in root.rglob("*")
        if path.is_file()
        and path.resolve() != manifest_path.resolve()
        and path.suffix in {".yaml", ".json"}
    }
    if set(paths) != discovered:
        raise TypedEvidenceContractError("Typed evidence manifest coverage is not exact.")
    calculated_hash = _canonical_content_hash(root, manifest, paths)
    if manifest.get("content_hash") != calculated_hash:
        raise TypedEvidenceContractError("Typed evidence content hash does not match the manifest.")

    spec_path = root / "typed_evidence_spec_v1.yaml"
    spec_schema_path = root / "schema" / "typed_evidence_spec_v1.schema.json"
    spec_document = _read_yaml(spec_path)
    _validate_schema(spec_document, _read_json(spec_schema_path), spec_path)
    return _spec_from_mapping(spec_document)


def _require_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not STABLE_TOKEN.fullmatch(value):
        raise TypedEvidenceContractError(f"{label} must be a stable non-narrative token.")
    return value


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _materialize_decimal(value: Any, label: str) -> str:
    return _decimal_string(_decimal(value, label))


def _materialize_measurement_rule(
    raw: Mapping[str, Any],
    spec: TypedEvidenceSpec,
    index: int,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise TypedEvidenceContractError(f"measurements[{index}] must be an object.")
    base = {
        "measurement_id",
        "kind",
        "role",
        "weight",
        "allowed_provenance",
    }
    kind = raw.get("kind")
    kind_fields = {
        "boolean": {"expected"},
        "count": {"direction", "minimum", "target", "maximum"},
        "bounded_frequency": {"direction", "minimum", "target", "maximum"},
        "ordinal": {"levels"},
        "duration": {"direction", "minimum", "target", "maximum", "unit"},
        "artifact": {"criteria"},
        "conceptual": {"criteria"},
        "scenario": {"criteria"},
        "objective": {"direction", "minimum", "target", "maximum", "unit"},
        "attestation": {"allowed_attestation_ids", "consent_required"},
    }
    if kind not in kind_fields or kind not in spec.measurement_kinds:
        raise TypedEvidenceContractError(f"measurements[{index}].kind is unsupported.")
    expected_fields = base | kind_fields[kind]
    if set(raw) != expected_fields:
        raise TypedEvidenceContractError(
            f"measurements[{index}] fields do not match the {kind} rule contract."
        )
    measurement_id = _require_token(raw["measurement_id"], f"measurements[{index}].measurement_id")
    role = raw["role"]
    if role not in {"primary", "supporting", "adverse", "context"}:
        raise TypedEvidenceContractError(f"{measurement_id}: measurement role is unsupported.")
    weight = _bounded_decimal(raw["weight"], f"{measurement_id}.weight")
    if role in {"primary", "supporting"} and weight <= 0:
        raise TypedEvidenceContractError(f"{measurement_id}: scored weight must be positive.")
    if role in {"adverse", "context"} and weight != 0:
        raise TypedEvidenceContractError(f"{measurement_id}: non-scored weight must be zero.")
    allowed_provenance = _unique_strings(
        raw["allowed_provenance"], f"{measurement_id}.allowed_provenance"
    )
    if not set(allowed_provenance).issubset(spec.provenance_kinds):
        raise TypedEvidenceContractError(f"{measurement_id}: provenance kind is unsupported.")

    result: dict[str, Any] = {
        "measurement_id": measurement_id,
        "kind": kind,
        "role": role,
        "weight": _decimal_string(weight),
        "allowed_provenance": list(allowed_provenance),
    }
    if kind == "boolean":
        if not isinstance(raw["expected"], bool):
            raise TypedEvidenceContractError(f"{measurement_id}.expected must be Boolean.")
        result["expected"] = raw["expected"]
    elif kind in {"count", "bounded_frequency", "duration", "objective"}:
        direction = raw["direction"]
        if direction not in {"at_least", "at_most"}:
            raise TypedEvidenceContractError(f"{measurement_id}.direction is unsupported.")
        minimum = _decimal(raw["minimum"], f"{measurement_id}.minimum")
        target = _decimal(raw["target"], f"{measurement_id}.target")
        maximum = _decimal(raw["maximum"], f"{measurement_id}.maximum")
        if not minimum <= target <= maximum or minimum == maximum:
            raise TypedEvidenceContractError(
                f"{measurement_id}: expected minimum <= target <= maximum with a range."
            )
        if kind in {"count", "duration"} and minimum < 0:
            raise TypedEvidenceContractError(f"{measurement_id}: values cannot be negative.")
        if kind == "bounded_frequency" and (minimum < 0 or maximum > 1):
            raise TypedEvidenceContractError(
                f"{measurement_id}: frequency bounds must remain in [0, 1]."
            )
        result.update(
            {
                "direction": direction,
                "minimum": _decimal_string(minimum),
                "target": _decimal_string(target),
                "maximum": _decimal_string(maximum),
            }
        )
        if kind in {"duration", "objective"}:
            result["unit"] = _require_token(raw["unit"], f"{measurement_id}.unit")
    elif kind == "ordinal":
        levels = raw["levels"]
        if not isinstance(levels, list) or len(levels) < 2:
            raise TypedEvidenceContractError(f"{measurement_id}.levels requires two levels.")
        materialized_levels = []
        ids: set[str] = set()
        for level_index, level in enumerate(levels):
            if not isinstance(level, Mapping) or set(level) != {"level_id", "score"}:
                raise TypedEvidenceContractError(
                    f"{measurement_id}.levels[{level_index}] is malformed."
                )
            level_id = _require_token(
                level["level_id"], f"{measurement_id}.levels[{level_index}].level_id"
            )
            if level_id in ids:
                raise TypedEvidenceContractError(f"{measurement_id}: duplicate ordinal level.")
            ids.add(level_id)
            materialized_levels.append(
                {
                    "level_id": level_id,
                    "score": _decimal_string(
                        _bounded_decimal(
                            level["score"],
                            f"{measurement_id}.levels[{level_index}].score",
                        )
                    ),
                }
            )
        result["levels"] = materialized_levels
    elif kind in {"artifact", "conceptual", "scenario"}:
        criteria = _unique_strings(raw["criteria"], f"{measurement_id}.criteria")
        result["criteria"] = [
            _require_token(item, f"{measurement_id}.criteria") for item in criteria
        ]
    elif kind == "attestation":
        attestation_ids = _unique_strings(
            raw["allowed_attestation_ids"],
            f"{measurement_id}.allowed_attestation_ids",
        )
        if not isinstance(raw["consent_required"], bool):
            raise TypedEvidenceContractError(f"{measurement_id}.consent_required must be Boolean.")
        result["allowed_attestation_ids"] = [
            _require_token(item, f"{measurement_id}.allowed_attestation_ids")
            for item in attestation_ids
        ]
        result["consent_required"] = raw["consent_required"]
    return result


def materialize_typed_evidence_rules(
    rules: Mapping[str, Any],
    spec: TypedEvidenceSpec,
) -> dict[str, Any]:
    if not isinstance(rules, Mapping) or set(rules) != {
        "schema_version",
        "max_age_days",
        "measurements",
        "competency_measurement_ids",
        "transfer_disposition",
    }:
        raise TypedEvidenceContractError(
            "Typed evidence rules fields do not match the accepted contract."
        )
    if rules["schema_version"] != TYPED_EVIDENCE_RULES_VERSION:
        raise TypedEvidenceContractError("Typed evidence rules version is unsupported.")
    max_age = rules["max_age_days"]
    if max_age is not None and (
        not isinstance(max_age, int) or isinstance(max_age, bool) or not 1 <= max_age <= 3650
    ):
        raise TypedEvidenceContractError("max_age_days must be null or an integer in 1..3650.")
    raw_measurements = rules["measurements"]
    if not isinstance(raw_measurements, list) or not raw_measurements:
        raise TypedEvidenceContractError("Typed evidence rules require measurements.")
    measurements = [
        _materialize_measurement_rule(raw, spec, index)
        for index, raw in enumerate(raw_measurements)
    ]
    ids = [item["measurement_id"] for item in measurements]
    if len(ids) != len(set(ids)):
        raise TypedEvidenceContractError("Typed evidence rules contain duplicate measurement IDs.")
    if not any(item["role"] == "primary" for item in measurements):
        raise TypedEvidenceContractError("Typed evidence rules require a primary measurement.")
    competency_measurement_ids = _unique_strings(
        rules["competency_measurement_ids"],
        "competency_measurement_ids",
        allow_empty=True,
    )
    unknown_competency_ids = set(competency_measurement_ids) - set(ids)
    if unknown_competency_ids:
        raise TypedEvidenceContractError("Competency rubric references unknown measurement IDs.")
    measurement_by_id = {item["measurement_id"]: item for item in measurements}
    invalid_competency_ids = [
        item
        for item in competency_measurement_ids
        if measurement_by_id[item]["role"] not in {"primary", "supporting"}
        or Decimal(measurement_by_id[item]["weight"]) <= 0
    ]
    if invalid_competency_ids:
        raise TypedEvidenceContractError(
            "Competency rubric may use only positively weighted primary/supporting measurements."
        )
    transfer_disposition = rules["transfer_disposition"]
    if transfer_disposition not in {
        "protocol_only",
        "context_bound",
        "cross_context_candidate",
    }:
        raise TypedEvidenceContractError("Transfer disposition is unsupported.")
    if transfer_disposition == "protocol_only" and competency_measurement_ids:
        raise TypedEvidenceContractError(
            "Protocol-only evidence cannot define competency measurements."
        )
    if transfer_disposition != "protocol_only" and not competency_measurement_ids:
        raise TypedEvidenceContractError(
            "Direct competency evidence requires competency measurements."
        )
    return {
        "schema_version": TYPED_EVIDENCE_RULES_VERSION,
        "max_age_days": max_age,
        "measurements": measurements,
        "competency_measurement_ids": list(competency_measurement_ids),
        "transfer_disposition": transfer_disposition,
    }


def _ratio_score(value: Decimal, rule: Mapping[str, Any]) -> Decimal:
    minimum = Decimal(rule["minimum"])
    target = Decimal(rule["target"])
    maximum = Decimal(rule["maximum"])
    if value < minimum or value > maximum:
        raise TypedEvidenceContractError(
            "Observed numeric value is outside its materialized rule bounds."
        )
    if rule["direction"] == "at_least":
        if target == minimum:
            return Decimal("1")
        return min(Decimal("1"), max(Decimal("0"), (value - minimum) / (target - minimum)))
    if maximum == target:
        return Decimal("1")
    return min(Decimal("1"), max(Decimal("0"), (maximum - value) / (maximum - target)))


def _measurement_score(
    observation: TypedObservationInput,
    rule: Mapping[str, Any],
) -> tuple[Decimal, Any]:
    if observation.state != "observed":
        if observation.value is not None:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: only observed values may carry a value."
            )
        return Decimal("0"), None
    if observation.value is None:
        raise TypedEvidenceContractError(
            f"{observation.measurement_id}: an observed value is required."
        )

    kind = observation.kind
    value = observation.value
    if kind == "boolean":
        if not isinstance(value, bool):
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: Boolean measurement requires true or false."
            )
        return (Decimal("1") if value == rule["expected"] else Decimal("0")), value
    if kind == "count":
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: count requires a nonnegative integer."
            )
        return _ratio_score(Decimal(value), rule), value
    if kind == "bounded_frequency":
        if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: frequency requires numerator and denominator."
            )
        numerator = value["numerator"]
        denominator = value["denominator"]
        if (
            not isinstance(numerator, int)
            or isinstance(numerator, bool)
            or not isinstance(denominator, int)
            or isinstance(denominator, bool)
            or denominator <= 0
            or numerator < 0
            or numerator > denominator
        ):
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: bounded frequency is invalid."
            )
        normalized = Decimal(numerator) / Decimal(denominator)
        return _ratio_score(normalized, rule), {
            "numerator": numerator,
            "denominator": denominator,
        }
    if kind == "ordinal":
        level_id = _require_token(value, f"{observation.measurement_id}.value")
        levels = {item["level_id"]: Decimal(item["score"]) for item in rule["levels"]}
        if level_id not in levels:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: ordinal level is not in the rule."
            )
        return levels[level_id], level_id
    if kind == "duration":
        if not isinstance(value, Mapping) or set(value) != {"amount", "unit"}:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: duration requires amount and unit."
            )
        if value["unit"] != rule["unit"]:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: duration unit does not match the rule."
            )
        amount = _decimal(value["amount"], f"{observation.measurement_id}.amount")
        if amount < 0:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: duration cannot be negative."
            )
        return _ratio_score(amount, rule), {
            "amount": _decimal_string(amount),
            "unit": value["unit"],
        }
    if kind in {"artifact", "conceptual", "scenario"}:
        if not isinstance(value, Mapping) or set(value) != {"criteria_met"}:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: rubric value requires criteria_met."
            )
        criteria_met = _unique_strings(
            value["criteria_met"],
            f"{observation.measurement_id}.criteria_met",
            allow_empty=True,
        )
        if not set(criteria_met).issubset(rule["criteria"]):
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: rubric contains an unknown criterion."
            )
        score = Decimal(len(criteria_met)) / Decimal(len(rule["criteria"]))
        return score, {"criteria_met": list(criteria_met)}
    if kind == "objective":
        if not isinstance(value, Mapping) or set(value) != {"amount", "unit"}:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: objective value requires amount and unit."
            )
        if value["unit"] != rule["unit"]:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: objective unit does not match the rule."
            )
        amount = _decimal(value["amount"], f"{observation.measurement_id}.amount")
        return _ratio_score(amount, rule), {
            "amount": _decimal_string(amount),
            "unit": value["unit"],
        }
    if kind == "attestation":
        if not isinstance(value, Mapping) or set(value) != {
            "attestation_id",
            "consent_confirmed",
        }:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: attestation value is malformed."
            )
        attestation_id = _require_token(
            value["attestation_id"], f"{observation.measurement_id}.attestation_id"
        )
        if not isinstance(value["consent_confirmed"], bool):
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: consent confirmation must be Boolean."
            )
        valid = attestation_id in rule["allowed_attestation_ids"]
        if rule["consent_required"]:
            valid = valid and value["consent_confirmed"]
        return (Decimal("1") if valid else Decimal("0")), {
            "attestation_id": attestation_id,
            "consent_confirmed": value["consent_confirmed"],
        }
    raise TypedEvidenceContractError(f"{observation.measurement_id}: unsupported kind.")


def _weighted_role_score(
    scores: Sequence[tuple[Mapping[str, Any], Decimal]],
    role: str,
) -> Decimal:
    selected = [(rule, score) for rule, score in scores if rule["role"] == role]
    if not selected:
        return Decimal("0")
    total_weight = sum((Decimal(rule["weight"]) for rule, _ in selected), Decimal("0"))
    if total_weight <= 0:
        return Decimal("0")
    return (
        sum(
            (Decimal(rule["weight"]) * score for rule, score in selected),
            Decimal("0"),
        )
        / total_weight
    )


def evaluate_typed_evidence(
    evidence: TypedEvidenceInput,
    rules: Mapping[str, Any],
    *,
    spec: TypedEvidenceSpec | None = None,
) -> TypedEvidenceResult:
    if not isinstance(evidence, TypedEvidenceInput):
        raise TypedEvidenceContractError(
            "Typed evidence input must use the accepted input contract."
        )
    if spec is None:
        resolved_spec = load_typed_evidence_spec()
    else:
        if not isinstance(spec, TypedEvidenceSpec):
            raise TypedEvidenceContractError(
                "Typed evidence spec must use the accepted spec contract."
            )
        try:
            resolved_spec = _spec_from_mapping(spec.materialized())
        except TypedEvidenceContractError:
            raise
        except (ArithmeticError, AttributeError, TypeError, ValueError) as exc:
            raise TypedEvidenceContractError(
                "Typed evidence spec does not canonically materialize."
            ) from exc
    materialized_rules = materialize_typed_evidence_rules(rules, resolved_spec)
    for label, value in (
        ("event_key", evidence.event_key),
        ("origin_key", evidence.origin_key),
        ("assessment_epoch_id", evidence.assessment_epoch_id),
        ("protocol_stable_id", evidence.protocol_stable_id),
        ("action_stable_id", evidence.action_stable_id),
        ("competency_stable_id", evidence.competency_stable_id),
        ("scoring_policy_id", evidence.scoring_policy_id),
        ("context_key", evidence.context_key),
    ):
        _require_token(value, label)
    if evidence.scoring_policy_id not in SUPPORTED_SCORING_POLICY_IDS:
        raise TypedEvidenceContractError("Scoring policy is not part of the typed contract.")
    if not isinstance(evidence.action_attempted, bool) or not isinstance(
        evidence.action_completed,
        bool,
    ):
        raise TypedEvidenceContractError("Action attempted and completed values must be Boolean.")
    if evidence.action_completed and not evidence.action_attempted:
        raise TypedEvidenceContractError("A completed action must also be attempted.")
    if (
        not isinstance(evidence.repetition_index, int)
        or isinstance(evidence.repetition_index, bool)
        or evidence.repetition_index < 1
    ):
        raise TypedEvidenceContractError("Repetition index must be a positive non-Boolean integer.")
    if not isinstance(evidence.support_level, str):
        raise TypedEvidenceContractError("Support level must be a string token.")
    if evidence.support_level not in resolved_spec.support_factor_map:
        raise TypedEvidenceContractError("Support level is not part of the typed contract.")
    if not isinstance(evidence.context_comparison, str):
        raise TypedEvidenceContractError("Context comparison must be a string token.")
    if evidence.context_comparison not in resolved_spec.context_factor_map:
        raise TypedEvidenceContractError("Context comparison is not part of the typed contract.")
    if not isinstance(evidence.evidence_direction, str):
        raise TypedEvidenceContractError("Evidence direction must be a string token.")
    if evidence.evidence_direction not in resolved_spec.evidence_directions:
        raise TypedEvidenceContractError("Evidence direction is not part of the typed contract.")
    if not isinstance(evidence.adverse_indicator_ids, (tuple, list)):
        raise TypedEvidenceContractError("Adverse indicator IDs must be a structured sequence.")
    adverse_ids = tuple(
        _require_token(item, "adverse_indicator_ids") for item in evidence.adverse_indicator_ids
    )
    if len(adverse_ids) != len(set(adverse_ids)):
        raise TypedEvidenceContractError("Adverse indicator IDs contain duplicates.")
    try:
        observed_on = date.fromisoformat(evidence.observed_on)
        as_of = date.fromisoformat(evidence.as_of_date)
    except (TypeError, ValueError) as exc:
        raise TypedEvidenceContractError("Observed and as-of dates must use ISO dates.") from exc
    if observed_on > as_of:
        raise TypedEvidenceContractError("Observed date cannot be after the as-of date.")

    rule_by_id = {item["measurement_id"]: item for item in materialized_rules["measurements"]}
    if not isinstance(evidence.observations, (tuple, list)):
        raise TypedEvidenceContractError("Typed observations must be a structured sequence.")
    observations = tuple(evidence.observations)
    if any(not isinstance(item, TypedObservationInput) for item in observations):
        raise TypedEvidenceContractError(
            "Every typed observation must use the accepted observation contract."
        )
    for observation in observations:
        _require_token(observation.measurement_id, "observation.measurement_id")
        _require_token(observation.kind, f"{observation.measurement_id}.kind")
        _require_token(observation.state, f"{observation.measurement_id}.state")
        _require_token(
            observation.provenance_kind,
            f"{observation.measurement_id}.provenance_kind",
        )
    ids = [item.measurement_id for item in observations]
    if len(ids) != len(set(ids)):
        raise TypedEvidenceContractError("Typed evidence contains duplicate measurement IDs.")
    if set(ids) != set(rule_by_id):
        raise TypedEvidenceContractError(
            "Typed evidence must explicitly cover every materialized measurement rule."
        )

    scored: list[tuple[Mapping[str, Any], Decimal]] = []
    score_by_measurement: dict[str, Decimal] = {}
    state_by_measurement: dict[str, str] = {}
    materialized_observations = []
    provenance: set[str] = set()
    adverse_from_measurement = False
    invalid_attestation_ids: list[str] = []
    observed_count = 0
    for observation in sorted(observations, key=lambda item: item.measurement_id):
        rule = rule_by_id[observation.measurement_id]
        if observation.kind != rule["kind"]:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: input kind does not match its rule."
            )
        if observation.state not in resolved_spec.observation_states:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: observation state is unsupported."
            )
        if observation.provenance_kind not in resolved_spec.provenance_kinds:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: provenance kind is unsupported."
            )
        if observation.provenance_kind not in rule["allowed_provenance"]:
            raise TypedEvidenceContractError(
                f"{observation.measurement_id}: provenance is not allowed by its rule."
            )
        score, materialized_value = _measurement_score(observation, rule)
        scored.append((rule, score))
        score_by_measurement[observation.measurement_id] = score
        state_by_measurement[observation.measurement_id] = observation.state
        if observation.state == "observed":
            observed_count += 1
            provenance.add(observation.provenance_kind)
        if rule["role"] == "adverse" and observation.state == "observed" and score > 0:
            adverse_from_measurement = True
        if rule["kind"] == "attestation" and observation.state == "observed" and score == 0:
            invalid_attestation_ids.append(observation.measurement_id)
        materialized_observations.append(
            {
                "measurement_id": observation.measurement_id,
                "kind": observation.kind,
                "state": observation.state,
                "provenance_kind": observation.provenance_kind,
                "value": materialized_value,
                "normalized_score": _decimal_string(_quantize(score)),
            }
        )

    primary = _weighted_role_score(scored, "primary")
    supporting = _weighted_role_score(scored, "supporting")
    performance = Decimal("0")
    if evidence.action_attempted:
        performance += resolved_spec.performance_attempt_weight
    if evidence.action_completed:
        performance += resolved_spec.performance_completion_weight
    performance += resolved_spec.performance_primary_weight * primary
    performance += resolved_spec.performance_supporting_weight * supporting
    performance = _quantize(min(Decimal("1"), performance))

    quality = resolved_spec.quality_base
    if evidence.action_attempted:
        quality += resolved_spec.quality_attempt_bonus
    if evidence.evidence_direction != "unknown":
        quality += resolved_spec.quality_direction_bonus
    if evidence.support_level != "not_recorded":
        quality += resolved_spec.quality_support_bonus
    quality += resolved_spec.quality_context_bonus
    if observed_count:
        quality += resolved_spec.quality_observed_bonus
    quality = _quantize(min(resolved_spec.quality_cap, quality))

    independence = resolved_spec.support_factor_map[evidence.support_level]
    context_breadth = resolved_spec.context_factor_map[evidence.context_comparison]
    repeat_position = min(
        evidence.repetition_index,
        len(resolved_spec.repetition_multipliers),
    )
    repetition = resolved_spec.repetition_multipliers[repeat_position - 1]
    base_mass = _quantize(quality * independence * context_breadth * repetition)
    contradiction = {
        "supports": Decimal("0"),
        "mixed": Decimal("0.5"),
        "contradicts": Decimal("1"),
        "inconclusive": Decimal("0"),
        "unknown": None,
    }[evidence.evidence_direction]

    max_age = materialized_rules["max_age_days"]
    age_days = (as_of - observed_on).days
    recency_status = "stale" if max_age is not None and age_days > max_age else "current"
    adverse = bool(adverse_ids) or adverse_from_measurement
    competency_ids = materialized_rules["competency_measurement_ids"]
    observed_competency_ids = [
        item for item in competency_ids if state_by_measurement[item] == "observed"
    ]
    if observed_competency_ids:
        total_competency_weight = sum(
            (Decimal(rule_by_id[item]["weight"]) for item in observed_competency_ids),
            Decimal("0"),
        )
        competency_performance = _quantize(
            sum(
                (
                    score_by_measurement[item] * Decimal(rule_by_id[item]["weight"])
                    for item in observed_competency_ids
                ),
                Decimal("0"),
            )
            / total_competency_weight
        )
    else:
        competency_performance = None
    withholding: list[str] = []
    if not evidence.action_attempted:
        withholding.append("action_not_attempted")
    if evidence.evidence_direction in {"unknown", "inconclusive"}:
        withholding.append(f"direction_{evidence.evidence_direction}")
    if recency_status == "stale":
        withholding.append("stale_at_explicit_as_of_date")
    if adverse:
        withholding.append("adverse_outcome_requires_review")
    if not observed_count:
        withholding.append("no_observed_measurement")
    if competency_ids and not observed_competency_ids:
        withholding.append("no_observed_competency_measurement")
    withholding.extend(
        f"invalid_or_unconsented_attestation:{measurement_id}"
        for measurement_id in sorted(invalid_attestation_ids)
    )

    materialized_spec = resolved_spec.materialized()
    snapshot = {
        "algorithm_version": TYPED_EVIDENCE_ALGORITHM_VERSION,
        "event_key": evidence.event_key,
        "origin_key": evidence.origin_key,
        "assessment_epoch_id": evidence.assessment_epoch_id,
        "protocol_stable_id": evidence.protocol_stable_id,
        "action_stable_id": evidence.action_stable_id,
        "competency_stable_id": evidence.competency_stable_id,
        "scoring_policy_id": evidence.scoring_policy_id,
        "action_attempted": evidence.action_attempted,
        "action_completed": evidence.action_completed,
        "observations": materialized_observations,
        "support_level": evidence.support_level,
        "context_comparison": evidence.context_comparison,
        "context_key": evidence.context_key,
        "evidence_direction": evidence.evidence_direction,
        "adverse_indicator_ids": list(adverse_ids),
        "repetition_index": evidence.repetition_index,
        "observed_on": observed_on.isoformat(),
        "as_of_date": as_of.isoformat(),
        "materialized_spec": materialized_spec,
        "materialized_spec_hash": _canonical_object_hash(materialized_spec),
        "materialized_rules": materialized_rules,
        "materialized_rules_hash": _canonical_object_hash(materialized_rules),
    }
    explanation = {
        "protocol_performance": (
            "Protocol performance describes the bounded action only; it is not competency mastery."
        ),
        "quality": (
            "Quality reflects structured completeness, never free-text length, sentiment, "
            "or personal worth."
        ),
        "provenance": (
            "Provenance is recorded separately from measurement kind and does not by itself "
            "prove accuracy."
        ),
        "direction": (
            "Contradiction remains directional evidence; adverse outcomes are separately "
            "withheld for review."
        ),
        "recency": (
            f"Recency was evaluated deterministically at {as_of.isoformat()} "
            f"from an observation dated {observed_on.isoformat()}."
        ),
    }
    return TypedEvidenceResult(
        algorithm_version=TYPED_EVIDENCE_ALGORITHM_VERSION,
        performance=performance,
        quality=quality,
        independence=_quantize(independence),
        context_breadth=_quantize(context_breadth),
        repetition_index=evidence.repetition_index,
        repetition_multiplier=_quantize(repetition),
        contradiction_level=(None if contradiction is None else _quantize(contradiction)),
        base_evidence_mass=base_mass,
        direction=evidence.evidence_direction,
        adverse=adverse,
        recency_status=recency_status,
        provenance_kinds=tuple(sorted(provenance)),
        competency_performance=competency_performance,
        transfer_disposition=materialized_rules["transfer_disposition"],
        withholding_reasons=tuple(withholding),
        input_snapshot=snapshot,
        explanation=explanation,
    )


def replay_typed_evidence(input_snapshot: Mapping[str, Any]) -> TypedEvidenceResult:
    try:
        if input_snapshot["algorithm_version"] != TYPED_EVIDENCE_ALGORITHM_VERSION:
            raise TypedEvidenceContractError(
                "Typed evidence snapshot algorithm version is unsupported."
            )
        materialized_spec = input_snapshot["materialized_spec"]
        materialized_rules = input_snapshot["materialized_rules"]
        if input_snapshot["materialized_spec_hash"] != _canonical_object_hash(materialized_spec):
            raise TypedEvidenceContractError(
                "Typed evidence materialized spec hash does not verify."
            )
        if input_snapshot["materialized_rules_hash"] != _canonical_object_hash(materialized_rules):
            raise TypedEvidenceContractError(
                "Typed evidence materialized rules hash does not verify."
            )
        spec = _spec_from_mapping(materialized_spec)
        observations = tuple(
            TypedObservationInput(
                measurement_id=item["measurement_id"],
                kind=item["kind"],
                state=item["state"],
                provenance_kind=item["provenance_kind"],
                value=item["value"],
            )
            for item in input_snapshot["observations"]
        )
        evidence = TypedEvidenceInput(
            event_key=input_snapshot["event_key"],
            origin_key=input_snapshot["origin_key"],
            assessment_epoch_id=input_snapshot["assessment_epoch_id"],
            protocol_stable_id=input_snapshot["protocol_stable_id"],
            action_stable_id=input_snapshot["action_stable_id"],
            competency_stable_id=input_snapshot["competency_stable_id"],
            scoring_policy_id=input_snapshot["scoring_policy_id"],
            action_attempted=input_snapshot["action_attempted"],
            action_completed=input_snapshot["action_completed"],
            observations=observations,
            support_level=input_snapshot["support_level"],
            context_comparison=input_snapshot["context_comparison"],
            context_key=input_snapshot["context_key"],
            evidence_direction=input_snapshot["evidence_direction"],
            adverse_indicator_ids=tuple(input_snapshot["adverse_indicator_ids"]),
            repetition_index=input_snapshot["repetition_index"],
            observed_on=input_snapshot["observed_on"],
            as_of_date=input_snapshot["as_of_date"],
        )
        rules = materialized_rules
    except TypedEvidenceContractError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise TypedEvidenceContractError(
            "Typed evidence snapshot is incomplete or malformed."
        ) from exc
    result = evaluate_typed_evidence(evidence, rules, spec=spec)
    if result.input_snapshot != input_snapshot:
        raise TypedEvidenceContractError("Typed evidence snapshot is not canonically materialized.")
    return result
