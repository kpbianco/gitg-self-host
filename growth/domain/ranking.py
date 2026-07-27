from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from growth.domain.scoring import WEIGHT_TOLERANCE

RANKING_ALGORITHM_VERSION = "GG-NEED-RANKING-1.0"
NEED_EXPONENT = Decimal("1.5")
CONFIDENCE_FLOOR = Decimal("0.60")
CONFIDENCE_WEIGHT = Decimal("0.40")
FOUR_PLACES = Decimal("0.0001")


class RankingContractError(ValueError):
    pass


@dataclass(frozen=True)
class RankedNeed:
    lever_id: str
    score: Decimal | None
    rank: int


@dataclass(frozen=True)
class ProtocolWeight:
    lever_id: str
    weight: Decimal


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _require_unit_interval(value: Decimal, label: str) -> None:
    if not value.is_finite() or value < 0 or value > 1:
        raise RankingContractError(f"{label} must be a finite value from 0 to 1.")


def provisional_need_score(
    estimate: Decimal | None,
    confidence: Decimal,
) -> Decimal | None:
    """Reproduce assessment v1.1's provisional need function.

    Applicability, importance, readiness, and urgency are not collected as
    separate per-user inputs yet. M3B therefore updates the same provisional
    gap-and-confidence score that initialized the assessment ranking.
    """

    _require_unit_interval(confidence, "Evidence confidence")
    if estimate is None:
        return None
    _require_unit_interval(estimate, "Current estimate")
    gap = Decimal("1") - estimate
    with localcontext() as context:
        context.prec = 28
        powered_gap = gap * gap.sqrt()
        confidence_factor = CONFIDENCE_FLOOR + CONFIDENCE_WEIGHT * confidence
        return _quantize(powered_gap * confidence_factor)


def rank_needs(
    values: Mapping[str, tuple[Decimal | None, Decimal]],
) -> tuple[RankedNeed, ...]:
    if not values:
        raise RankingContractError("Need ranking requires at least one stable lever ID.")
    rows = []
    for lever_id, (estimate, confidence) in values.items():
        if not lever_id:
            raise RankingContractError("Need ranking requires stable lever IDs.")
        rows.append((lever_id, provisional_need_score(estimate, confidence)))
    rows.sort(
        key=lambda item: (
            item[1] is None,
            -(item[1] or Decimal("0")),
            item[0],
        )
    )
    return tuple(
        RankedNeed(lever_id=lever_id, score=score, rank=index)
        for index, (lever_id, score) in enumerate(rows, start=1)
    )


def protocol_priority(
    needs: Mapping[str, Decimal | None],
    weights: Iterable[ProtocolWeight],
) -> Decimal:
    resolved = tuple(weights)
    if not resolved:
        raise RankingContractError("A ranked practice requires canonical lever weights.")
    lever_ids = [item.lever_id for item in resolved]
    if len(lever_ids) != len(set(lever_ids)):
        raise RankingContractError("A ranked practice contains duplicate stable lever IDs.")
    total_weight = Decimal("0")
    total_priority = Decimal("0")
    for item in resolved:
        if not item.lever_id:
            raise RankingContractError("Every practice weight requires a stable lever ID.")
        if not item.weight.is_finite() or item.weight <= 0 or item.weight > 1:
            raise RankingContractError(
                f"{item.lever_id}: practice weight must be a finite value in (0, 1]."
            )
        if item.lever_id not in needs:
            raise RankingContractError(
                f"{item.lever_id}: current need is unavailable for practice ranking."
            )
        need = needs[item.lever_id]
        total_weight += item.weight
        if need is not None:
            _require_unit_interval(need, f"{item.lever_id} current need")
            total_priority += item.weight * need
    if abs(total_weight - Decimal("1")) > WEIGHT_TOLERANCE:
        raise RankingContractError(
            f"Practice-to-lever weights sum to {total_weight}; expected approximately 1.0."
        )
    return _quantize(total_priority)
