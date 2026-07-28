from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from growth.domain.evidence import (
    EVIDENCE_ALGORITHM_VERSION,
    EvidenceContractError,
    replay_evidence,
)

TYPED_EVIDENCE_ALGORITHM_VERSION = "GG-TYPED-EVIDENCE-1.0"


class EvidenceDispatchError(EvidenceContractError):
    """Raised before snapshot parsing when an evidence version is unsupported."""


def _replay_typed_evidence(input_snapshot: Mapping[str, Any]) -> Any:
    # Imported lazily so the frozen GG-EVIDENCE-1.0 replay path has no
    # dependency on the additive typed contract.
    from growth.domain.typed_evidence import (
        TYPED_EVIDENCE_ALGORITHM_VERSION as IMPLEMENTED_TYPED_VERSION,
    )
    from growth.domain.typed_evidence import (
        TypedEvidenceContractError,
        replay_typed_evidence,
    )

    if IMPLEMENTED_TYPED_VERSION != TYPED_EVIDENCE_ALGORITHM_VERSION:
        raise EvidenceDispatchError("Typed evidence dispatcher version drifted.")
    try:
        return replay_typed_evidence(input_snapshot)
    except TypedEvidenceContractError as exc:
        raise EvidenceDispatchError(str(exc)) from exc


_REPLAY_HANDLERS: dict[str, Callable[[Mapping[str, Any]], Any]] = {
    EVIDENCE_ALGORITHM_VERSION: replay_evidence,
    TYPED_EVIDENCE_ALGORITHM_VERSION: _replay_typed_evidence,
}


def replay_evidence_by_version(
    algorithm_version: str,
    input_snapshot: Mapping[str, Any],
) -> Any:
    """Replay an immutable snapshot with its exact versioned implementation.

    Dispatch occurs before any handler reads the snapshot. Unknown versions
    therefore fail closed without accidentally applying the legacy parser.
    """

    try:
        handler = _REPLAY_HANDLERS[algorithm_version]
    except KeyError as exc:
        raise EvidenceDispatchError(
            f"Unsupported evidence algorithm_version: {algorithm_version!r}."
        ) from exc
    return handler(input_snapshot)
