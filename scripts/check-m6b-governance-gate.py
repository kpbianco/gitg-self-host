#!/usr/bin/env python3
"""Fail unless the real M6B specialist and research-gap records are complete."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def one(items: list[dict], key: str, value: str) -> dict:
    matches = [item for item in items if item.get(key) == value]
    if len(matches) != 1:
        raise ValueError(f"expected one {key}={value}, found {len(matches)}")
    return matches[0]


def main() -> int:
    reviews = yaml.safe_load((ROOT / "data/practices/expert_review_queue.yaml").read_text())[
        "reviews"
    ]
    gaps = yaml.safe_load((ROOT / "data/practices/research_gaps.yaml").read_text())["gaps"]
    review = one(reviews, "review_id", "ER-M6A-003")
    gap = one(gaps, "gap_id", "RG-M6A-002")
    errors: list[str] = []
    if review.get("status") != "complete":
        errors.append("ER-M6A-003 status is not complete")
    required = set(review.get("required_roles") or [])
    completed = set(review.get("completed_roles") or [])
    if required != completed:
        missing = sorted(required - completed)
        extra = sorted(completed - required)
        errors.append(f"ER-M6A-003 completed roles differ: missing={missing} extra={extra}")
    if not review.get("completed_on"):
        errors.append("ER-M6A-003 completed_on is absent")
    if not review.get("decision_reference"):
        errors.append("ER-M6A-003 decision_reference is absent")
    if gap.get("status") != "resolved":
        errors.append("RG-M6A-002 status is not resolved")
    if (
        "ER-M6A-003" not in str(gap.get("current_evidence", ""))
        and "decision" not in str(gap.get("current_evidence", "")).lower()
    ):
        errors.append("RG-M6A-002 current_evidence does not cite the completed governance decision")
    if errors:
        print("M6B governance gate is not satisfied:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("M6B governance gate satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
