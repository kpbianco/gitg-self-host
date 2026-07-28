# M3A shadow scoring contract

## Scope

M3A turns the reviewed M2 evidence events into a deterministic, versioned
posterior projection without changing stored profile or recommendation state.
The algorithm version is:

```text
GG-SCORING-SHADOW-1.0
```

The authenticated profile page labels the result as a preview. No M3A request,
practice transition, management command, migration, or seed operation writes a
current mastery score, current confidence, need, task priority, archetype,
orientation, recommendation, or score snapshot.

M3A was the review gate for the direction and confidence semantics. The
contract was accepted before M3B state activation began.

## Exact inputs

A projection uses:

- baseline assessment alpha and beta mass for the current assessment run;
- immutable, replay-verified `GG-EVIDENCE-1.0` events from a sprint linked to
  that same assessment run;
- a stable practice-to-competency link;
- the competency's canonical structured lever weights and each lever's
  canonical total mapped weight.

The first protocol is explicitly linked to competency `17.03`, **Maintaining
friendship**. Its structured weights are:

| Lever | Weight |
|---|---:|
| L26 — Friendship, Belonging, and Hospitality | 0.65 |
| L10 — Discipline, Habits, and Follow-Through | 0.15 |
| L23 — Communication and Listening | 0.10 |
| L24 — Empathy, Social Perception, and Perspective-Taking | 0.10 |

They sum to 1.0. Scoring weights are distinct from the protocol's existing
three recommendation targets; M3A does not broaden recommendation eligibility.
Seeding requires recommendation targets to be a non-empty subset of the
parent competency mapping. Runtime scoring never parses the human-readable
Notion `Lever Mapping` string.

Drafts have no evidence event and cannot enter a projection. Practice
completion and final review alone do not enter a projection.

## Baseline mass

Newly taken or imported assessments persist the canonical browser scorer's
six-decimal alpha and beta values on each `LeverBaseline`. Django validates
that alpha, beta, raw self-report, calibrated estimate, and evidence mass agree
with the v1.1 prior and equations before saving.

Pilot 002 publishes rounded raw and calibrated values but not alpha and beta.
M3A reconstructs mass only when those two published values uniquely identify
it under the canonical equal priors:

```text
alpha = 0.35 + mass × raw
beta  = 0.35 + mass × (1 - raw)
estimate = alpha / (alpha + beta)
```

The source is recorded as `published_reconstruction`. A neutral published pair
such as raw `0.5000` and estimate `0.5000` does not identify mass and remains
unavailable. The projection fails closed if any lever required by a practice
lacks an assessed estimate or identifiable baseline mass. M3A does not invent
a mass from confidence.

## Task-to-lever allocation

For event `t` and lever `l`:

```text
k_tl = min(1.5, 24 × w_tl / D_l)
potential_evidence_tl = base_event_mass × k_tl
```

`w_tl` is the structured task weight and `D_l` is the canonical total mapped
competency weight for the lever. The M2 event already includes quality,
independence, bounded context breadth, and repetition. M3A does not apply
those factors a second time.

The implementation uses decimal arithmetic with round-half-up semantics:
coefficients and mass terms are fixed to six decimal places, while displayed
estimates and confidence are fixed to four. The golden fixture locks this
rounding order as part of the algorithm version.

## Accepted direction policy

Protocol performance and evidence direction remain separate inputs. Direction
controls how much recorded performance may become success mass:

| Evidence direction | Direction multiplier | Scoring behavior |
|---|---:|---|
| Supports expected pattern | 1.0 | Use recorded protocol performance |
| Mixed or unclear | 0.5 | Use half of recorded performance |
| Contradicts expected pattern | 0.0 | Allocate the event entirely to failure mass |
| Not enough happened to tell | — | Withhold from posterior and confidence |
| Legacy direction not recorded | — | Withhold from posterior and confidence |

For an included event:

```text
effective_performance = performance × direction_multiplier
evidence_tl = potential_evidence_tl
success_tl = evidence_tl × effective_performance
failure_tl = evidence_tl - success_tl
```

This policy never converts missing direction into supportive evidence.
Contradiction retains the event's quality and total mass while routing that
mass away from success. Inconclusive and legacy-unknown events stay visible in
the evidence ledger but cannot move a shadow score.

## Posterior and confidence

For baseline alpha `S0_l`, baseline beta `F0_l`, and included contributions:

```text
alpha'_l = S0_l + sum(success_tl)
beta'_l  = F0_l + sum(failure_tl)
M'_l     = alpha'_l / (alpha'_l + beta'_l)
```

The posterior equation matches the canonical assessment scorer's dormant
task-evidence reference. Its confidence line cannot be carried over directly:
initial assessment confidence includes coverage, response quality, and
consistency, while the dormant line recalculates confidence only from
alpha/beta mass. Applying it after a first event can make displayed confidence
fall even though new included evidence was added. That violates the product
contract that confidence increases with evidence.

M3A therefore anchors confidence at the stored assessment value `C0_l` and
adds a bounded monotonic gain from newly included lever evidence `E_l`:

```text
C'_l = C0_l + (1 - C0_l) × E_l / (E_l + 1.5)
```

Zero included evidence leaves confidence exactly unchanged. Additional
included evidence cannot lower confidence or exceed 1.0. Inconclusive and
legacy-unknown events add zero `E_l`. This deliberate correction is versioned
and golden-tested; it does not change assessment v1.1 itself.

## Audit and tests

`tests/fixtures/scoring/shadow_v1.json` is a synthetic golden fixture covering
all five direction states and all four canonical weights. Tests require:

- exact coefficients, success/failure mass, posterior, and confidence;
- stable IDs and weights summing to approximately 1.0;
- duplicate-event and malformed-weight rejection;
- exact baseline-mass persistence for new assessment runs;
- conservative Pilot 002 reconstruction;
- draft exclusion and read-only profile rendering;
- unchanged stored profile state before and after projection.

The fixture is software calibration, not psychometric validation.

## M3B activation

M3A was approved without changing this mathematics. M3B retains the exact
algorithm version and adds immutable before/after snapshots, atomic and
idempotent state transitions, reversal/rebuild procedures, dynamic
provisional-need and recommendation tests, and an explicit baseline-only
upgrade policy. See `docs/scoring-state.md`.

## Proposed M6B parallel shadows

M6B does not route typed evidence through
`GG-SCORING-SHADOW-1.0`. It adds two distinct pure versions:

- `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` aggregates direct typed evidence for one
  canonical competency and assessment epoch;
- `GG-COMPETENCY-LEVER-SHADOW-1.0` projects each designated competency
  contribution once through the full canonical parent mapping.

There is no competency baseline in assessment v1.1. With no eligible direct
evidence, the competency shadow is unknown. A lever-derived competency summary
cannot enter the competency shadow or be projected back to levers.

The one-way lever shadow rejects duplicate event keys, malformed or duplicate
weights, and any attempt to use the recommendation-target subset as scoring
allocation. Unknown, inconclusive, not-observed, not-applicable, deferred,
policy-ineligible, adverse-withheld, and reversed evidence remains visible
with a stable withholding reason and contributes no mass. Reversing the only
active event restores the exact starting projection.

Old evidence stays attached to its original assessment epoch. A newer
assessment starts a new immutable lever baseline; M6B defines no automatic
carry-forward.

`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` is evaluated separately and remains
false for every new typed path in M6B. These shadows do not write
`LeverState`, `ScoreSnapshot`, need/rank, recommendation order, or the
activation ledger. Their fixtures are software invariants, not measurement or
psychometric validation.
