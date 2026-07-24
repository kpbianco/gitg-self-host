# Scoring Design — Deferred Implementation Reference

This document describes the intended algorithm. It is not authorization to enable score mutation in Milestone 1.

## Assessment response transform
For a 1–5 answer:

`x = (answer - 1) / 4`

N/A is excluded.

Assessment v1.1 maintains raw self-report, calibrated estimate, evidence confidence, and response-quality modifiers. The implementation in `data/assessment/` is the canonical reference for initial scoring.

## Task evidence event
An evidence event eventually contains:
- performance `p`;
- evidence quality `q`;
- independence `i`;
- context breadth `b`;
- repeat multiplier `r`;
- submitted/draft state;
- contradictory evidence.

Base evidence mass:

`e = q * i * b * r`

Repeat multipliers:
- first attempt: 1.00
- second: 0.65
- third: 0.40
- later: 0.25

For task `t` and lever `l`:

`k_tl = min(1.5, 24 * w_tl / D_l)`

where `w_tl` is task-to-lever weight and `D_l` is total mapped task weight for that lever.

Contributions:

`evidence_tl = e * k_tl`

`success_tl = e * p * k_tl`

`failure_tl = e * (1-p) * k_tl`

## Posterior mastery
With baseline success mass `S0_l`, baseline failure mass `F0_l`, and accumulated evidence:

`M_l = (S0_l + sum(success_tl)) / (S0_l + F0_l + sum(evidence_tl))`

Confidence increases with evidence but must remain bounded and separately displayed.

## Need and recommendation
A provisional need form:

`N_l = applicability * importance * readiness * urgency * confidence_factor * (1 - M_l)^1.5`

Task priority:

`P_t = sum_l(w_tl * N_l)`

Personality/orientation style fit may only apply a narrow presentation/tie-breaking modifier, historically ±5%.

## Required implementation properties
- pure function;
- deterministic;
- versioned;
- immutable input/output;
- auditable contribution breakdown;
- reversible via snapshots/events;
- exhaustive unit/property tests;
- no update from drafts;
- no update from completion alone.
