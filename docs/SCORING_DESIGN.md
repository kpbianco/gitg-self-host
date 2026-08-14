# Scoring Design — M3 evidence and current state

M2A implements only the event-level contract in `docs/evidence-contract.md`.
M2B adds ledger, export, replay-verification, and calibration surfaces around
those immutable events without changing their mathematics. M3A implements the
task-to-lever and posterior sections as `GG-SCORING-SHADOW-1.0`, a pure
read-only projection documented in `docs/scoring-shadow.md`. M3A itself did
not authorize profile mutation.

M3A was reviewed and accepted. M3B activates that exact mathematics for the
friendship protocol with separate current state and immutable transitions
under `docs/scoring-state.md`. It does not rewrite the browser assessment
scorer or the M2 event contract.

## Assessment response transform
For a 1–5 answer:

`x = (answer - 1) / 4`

N/A is excluded.

Assessment v1.1 maintains raw self-report, calibrated estimate, evidence confidence, and response-quality modifiers. The implementation in `data/assessment/` is the canonical reference for initial scoring.

## Task evidence event
`GG-EVIDENCE-1.0` now contains:
- performance `p`;
- evidence quality `q`;
- independence `i`;
- context breadth `b`;
- repeat multiplier `r`;
- submitted/draft state;
- contradictory evidence.

Base evidence mass:

`e = q * i * b * r`

M2A stores `e` on an immutable event. Quality is capped at `0.85` because the
source is structured self-report; independence and context factors are
explicit; repetition is scoped to the same stable action within one sprint;
and contradiction is retained separately. Exact constants and migration
semantics are binding in `docs/evidence-contract.md`.

The M2 event already contains the reviewed repeat multiplier. M3A does not
apply repetition, quality, independence, or context breadth a second time.

For task `t` and lever `l`:

`k_tl = min(1.5, 24 * w_tl / D_l)`

where `w_tl` is task-to-lever weight and `D_l` is the canonical total mapped
competency weight for that lever.

The first protocol references canonical competency `17.03` and uses its
structured four-lever mapping. The weights must sum to approximately 1.0.

Direction multiplier `d` is:

- supportive: `1.0`;
- mixed: `0.5`;
- contradictory: `0.0`;
- inconclusive or legacy direction-unknown: withheld from scoring.

For included events:

`evidence_tl = e * k_tl`

`effective_performance = p * d`

`success_tl = evidence_tl * effective_performance`

`failure_tl = evidence_tl - success_tl`

This preserves contradictory mass as failure rather than reducing quality or
silently treating it as positive. Inconclusive and direction-unknown events
remain auditable but do not increase posterior confidence.

## Posterior mastery
With baseline alpha/success mass `S0_l`, baseline beta/failure mass `F0_l`,
and accumulated included evidence:

`M_l = (S0_l + sum(success_tl)) / (S0_l + F0_l + sum(evidence_tl))`

Assessment confidence contains response quality, coverage, and consistency, so
it is not interchangeable with alpha/beta mass. The dormant task-evidence
helper's direct mass-only recalculation can lower displayed confidence after a
new event. M3A corrects that integration defect by anchoring at stored
assessment confidence `C0_l` and adding a bounded monotonic gain from newly
included evidence `E_l`:

`C_l = C0_l + (1 - C0_l) * E_l / (E_l + 1.5)`

Confidence remains bounded, cannot decrease when evidence is added, and is
separately displayed. Withheld evidence adds no confidence.

## Need and recommendation
The complete context-aware need design remains:

`N_l = applicability * importance * readiness * urgency * confidence_factor * (1 - M_l)^1.5`

Complete task priority remains:

`P_t = sum_l(w_tl * N_l)`

Personality/orientation style fit may only apply a narrow presentation/tie-breaking modifier, historically ±5%.

M3B did not collect applicability, importance, readiness, urgency, and
opportunity as separate per-user inputs. Its production profile path therefore
continues to use the existing assessment v1.1 provisional need function rather
than inventing them:

`N_l = (1 - M_l)^1.5 * (0.60 + 0.40 * C_l)`

`GG-NEED-RANKING-1.0` reproduces every assessment baseline need/rank and then
recalculates it from current estimate and confidence. Active protocol priority
uses `P_t = sum_l(w_tl * N_l)`. M3B applies no personality modifier.

M6C-03 adds a separate, backend-only `GG-CONTEXT-PRIORITY-1.0` result. It keeps
that unchanged protocol priority as its base and multiplies it only by seven
explicit context terms:

`P_context = P_t × A × I × R × U × O × C × (1 - B)`

Each provided 0–4 ordinal is divided by four before multiplication, and the
final product is quantized half-up to four places. Missing, N/A, and deferred
inputs are withheld rather than imputed. Season, Personal OS text,
orientation, archetype, and personality have no numeric effect. This pure
result does not replace `build_profile_summary`, write score state, or change
production recommendations in M6C-03.

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

M2A satisfies purity, determinism, versioning, immutable input/output, replay,
and draft exclusion at the event layer. M2B adds strict whole-database replay
verification, direction-complete golden cases, and a deterministic
privacy-minimized export. M3A adds stable task allocation, exact or
conservatively reconstructed baseline mass, explicit direction semantics, a
pure Decimal posterior, synthetic golden fixtures, and an authenticated
unsaved preview.

M3A deliberately has no score snapshot because it makes no score-state
transition. M3B adds a separate 37-row `LeverState`, full hashed immutable
snapshots, atomic idempotent application, deterministic replay and repair,
audited reversal, and dynamic recommendation tests. `LeverBaseline`,
orientation, and archetype values remain unchanged. Only the reviewed
friendship protocol is score-active.

## Proposed M6B typed competency shadow

M6B does not reinterpret the formulas above. Existing
`GG-EVIDENCE-1.0`, `GG-SCORING-SHADOW-1.0`,
`GG-SCORE-STATE-1.0`, and `GG-NEED-RANKING-1.0` remain exact.

Assessment v1.1 produces lever baselines only. It does not provide a
competency baseline. `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` therefore begins in
an explicit unknown state and aggregates only eligible, replay-verified
`GG-TYPED-EVIDENCE-1.0` contributions for one competency and assessment
epoch. A weighted summary of lever state is not direct competency evidence
and cannot seed or update this shadow.

`GG-COMPETENCY-LEVER-SHADOW-1.0` projects a designated competency
contribution once through the parent competency's complete canonical mapping.
It must reject duplicate immutable event keys and cannot also apply the
protocol-performance view of the same event. Recommendation-target levers do
not participate in allocation.

Typed values have no default polarity or scale. Each materialized
`typed-evidence-rules-v1` snapshot defines normalization, direction,
withholding, and any minimum evidence. Unknown, not-observed, inconclusive,
not-applicable, and deferred input contributes no success/failure mass.
Contradiction may contribute failure only under its explicit rule. Adverse
outcome is orthogonal and may withhold an event or trigger a safety stop
without silently becoming a negative competency result.

`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` is evaluated after evidence and shadow
projection. It requires satisfied policy/provenance rules, valid canonical
mapping, available lever baseline mass, cleared source/risk/specialist gates,
and an approved activation-ledger entry. M6B makes every new typed path
production-ineligible and writes no state.

The production fingerprint
`f7639a0c623f1baac9469f34fe49ca9e2eb0be8fc1c616ab662996b2e90bf2bf`
pins friendship's protocol and competency IDs, evidence/scoring/state
versions, recommendation targets, all three action IDs and sequences, exact
v1 evidence rules, and full allocation weights and lever totals. It is
separate from the legacy runtime projection and practice-catalog hashes.

The synthetic M6B fixtures demonstrate deterministic software behavior, not
psychometric calibration. Pending review `ER-M6A-003` blocks M6B acceptance
and mass authoring.
