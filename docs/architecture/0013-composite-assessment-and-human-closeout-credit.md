# ADR 0013 — Composite assessment and human-closeout credit

## Status

Accepted by owner on 2026-09-01 for `M6I-01-COMPOSITE-CLOSEOUT-SCORING`.
Measurement, accessibility, and privacy/safety specialist acceptance remains
pending in `ER-M6A-003`; `RG-M6A-002` remains open.

## Context

The original ADD prototype used a short assessment to bias weak areas, treated
bounded tasks as the completable unit, updated their parent traits only after
completion, and reranked the remaining tasks. The current runtime instead can
apply each eligible check-in directly to Bayesian lever state. That makes
incremental protocol evidence look like global capability progress before the
user has closed the practice, and it does not provide a direct, inspectable
completion-credit state for all 383 competencies.

The canonical model already contains seven lever families, 37 assessment
levers, 27 curriculum domains, 383 competencies, a normalized two-to-five
lever mapping for every competency, one runtime practice per competency, and
1,151 actions. Asking one assessment question for every competency would add
burden and false precision. Treating all mapped levers as equal would discard
reviewed relevance differences; using only the current weights would undercut
the original broad-parent-credit premise.

Completion must remain distinct from mastery. Check-ins must remain useful as
structured evidence and audit history without becoming automatic global score
updates.

## Decision

Introduce an additive versioned composite state alongside the frozen
`GG-SCORE-STATE-1.0` history.

### Assessment projection

Assessment v1.1 remains immutable. Its 37 lever estimates and family rollups
are the assessment-derived inputs. For every competency, blend its canonical
mapping with equal relationship share:

`w(c,l) = 0.50 * r(c,l) + 0.50 * (1 / k)`

The blended relationship remains positive and normalized. It preserves every
secondary relationship while allowing the canonical mapping to keep more
applicable relationships stronger.

Calculate a preliminary competency value from its blended lever relationships.
Calculate each domain as the equal mean of those preliminary values for the
domain's member competencies. Then calculate the final competency estimate:

`estimate(c) = 0.50 * mapped_lever(c) + 0.25 * mapped_family(c) + 0.25 * parent_domain(c)`

This two-stage order avoids a domain/competency cycle. The score is explicitly
an assessment-derived starting estimate, not direct competency evidence.
Existing v1.1 need and confidence mathematics initialize priority.

### Human closeout

Typed and legacy check-ins continue to create immutable evidence events. A new
composite-version sprint never routes those events into additive completion
state. The user explicitly marks action completion and later explicitly closes
the practice. The closeout transaction freezes completed action IDs, the
threshold, relationship version, calculation inputs, credit, and before/after
state hashes.

Actions are equal units in version 1. At the protocol's minimum completed count
the competency receives `0.75` completion credit. Completing all defined
actions receives `1.00`. If a future protocol permits an intermediate count,
interpolate linearly:

`credit = 0.75 + 0.25 * (completed - minimum) / (total - minimum)`

The minimum must be positive and less than or equal to total. When minimum
equals total, successful closeout receives `1.00`. A competency's current
credit is the maximum non-reversed closeout, not the sum of attempts.

### Propagation and priority

Lever coverage is the weighted mean of competency credit using `w(c,l)`.
Family coverage uses the same relationship mass grouped by family. Domain
coverage is the equal mean of its member competency credits. All results are
bounded in `[0,1]`, and full canonical coverage requires every contributing
competency to be full credit.

For starting need `A` and coverage `G`:

`remaining_need = A * sqrt(1 - G)`

Each candidate practice receives 50 percent mapped-lever remaining need,
25 percent mapped-family remaining need, and 25 percent parent-domain
remaining need. Its own `sqrt(1 - competency_credit)` factor prevents a
full-credit competency from immediately returning. The existing explicit
context-priority layer applies afterward without invented defaults.

Personally not-applicable coverage, if presented, uses a separately labeled
denominator. It never replaces or masquerades as canonical coverage.

### Version and history boundary

Existing assessment baselines, `LeverState`, `EvidenceEvent`, and
`ScoreSnapshot` records are never rewritten. Sprints carry an explicit scoring
contract version. Pre-migration sprints retain legacy replay. New sprints use
the composite closeout contract. Additive state has its own immutable event
and snapshot chain with deterministic initialization, processing, reversal,
rebuild, and assessment-epoch isolation.

## Consequences

- The concise assessment can initialize all 383 competency priorities without
  claiming direct measurement of all 383.
- A two-of-three closeout receives 75 percent credit; three of three receives
  full credit. The two four-action protocols analogously receive 75 percent at
  three of four and full credit at four of four.
- Check-ins remain auditable proof and can support the human action-completion
  decision, but they no longer create piecemeal global progress in new score
  epochs.
- Completing a related competency reduces shared lever and family need and
  therefore reranks the whole queue, preserving the useful behavior of the
  original prototype without its compounding bug.
- A repeated partial attempt does not accumulate past one. A later stronger
  closeout can raise the competency from `0.75` to `1.00` by a replayable
  delta.
- The extra family/domain/competency projections are correlated views of one
  assessment, not independent validating evidence. UI and documentation must
  say so.
- Decisions 047–049 do not become approved through this implementation.
  Their evidence-capture software may remain for audit compatibility, while
  their production-scoring architecture is superseded.
- Specialist and owner content governance remains separate. This ADR does not
  close `ER-M6A-003`, resolve `RG-M6A-002`, or validate interventions.
