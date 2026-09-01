# Versioned score-state contracts

## Scope

M3B first activated event-level mathematics for
`PRACTICE-FRIENDSHIP-01`, and M6F extended that historical architecture to all
383 canonical protocols. Decision 053 retains that complete history exactly
but prospectively routes new sprints through a separate assessment-composite,
human-closeout contract. The sections describing `GG-SCORE-STATE-1.0` below
are historical replay requirements, not the trigger for a new sprint.

Five versions remain explicit:

```text
GG-SCORING-SHADOW-1.0  posterior and confidence mathematics
GG-SCORE-STATE-1.0     persisted state and transition schema
GG-NEED-RANKING-1.0    provisional need and practice ordering
GG-PRODUCTION-SCORE-ELIGIBILITY-2.0  all-catalog production eligibility
GG-COMPOSITE-CLOSEOUT-SCORING-1.0    assessment priority and closeout credit
```

The word `SHADOW` remains in the scoring algorithm ID because M3B activates
the exact reviewed M3A contract instead of silently renaming or
reinterpreting it. The state and ranking layers have their own versions.

## Current composite and closeout boundary

Every supported assessment epoch receives one immutable composite projection
and one separate current composite state:

- 7 family rows, derived from the 37 assessment lever results;
- 37 lever rows, with explicit lower-confidence family inheritance when the
  concise assessment did not directly score a lever;
- 27 equal-member domain rollups; and
- 383 labeled assessment-derived competency estimates.

For a competency with `k` mapped levers, canonical weight `r(c,l)`, and
blended allocation `w(c,l)`:

```text
w(c,l) = 0.50 × r(c,l) + 0.50 × (1 / k)
estimate(c) = 0.50 × mapped_lever + 0.25 × mapped_family + 0.25 × parent_domain
```

These correlated projections initialize priority only; they are not 383
direct measurements and award no earned completion credit.

A current-version check-in always creates its immutable evidence event but
never changes composite score state. Only an explicit human final review may
close the whole practice and create one immutable `CompletionCreditEvent` in
the same transaction. Equal action units produce 0.75 credit at the configured
minimum (currently 2/3 or 3/4) and 1.00 when all defined actions are
complete. Repeated practices use the maximum active credit for the competency,
not a sum.

Lever and family coverage use normalized blended relationship mass; domain
coverage uses equal competency membership. Remaining need is:

```text
remaining_need = assessment_starting_need × sqrt(1 - completion_coverage)
```

Candidate priority combines 50% mapped-lever, 25% mapped-family, and 25%
parent-domain remaining need, then applies `sqrt(1 - competency_credit)` and
the unchanged explicit context layer. Full-credit competencies leave the
queue; related completion can rerank other competencies through shared
coverage.

`CompositeAssessmentSnapshot`, `CompletionCreditEvent`, and
`CompositeScoreSnapshot` are immutable. Initialization, process, reversal,
and repair are hashed and replayed independently from historical
`ScoreSnapshot` rows. Pre-migration sprints retain `GG-SCORE-STATE-1.0`; new
sprints default to `GG-COMPOSITE-CLOSEOUT-SCORING-1.0`.

Run or verify the current state with:

```bash
python manage.py rebuild_composite_score_state
python manage.py rebuild_composite_score_state --verify-only
make composite-scoring-check
```

## Immutable baseline and current state

`LeverBaseline` remains the immutable assessment starting point. M3B creates
one separate `LeverState` for each baseline and assessment run. A state holds:

- current alpha and beta mass;
- current provisional estimate and evidence confidence;
- cumulative included evidence mass and event count;
- current provisional need score and rank;
- scoring algorithm version;
- `active` or `baseline_only` status.

Historical assessment runs retain their own states. An event updates only the
assessment run recorded on its practice sprint. Taking a new assessment makes
that newer run the working profile; old evidence is not transferred to it.
Orientations, archetypes, raw self-report, calibrated baseline estimates, and
baseline need values never change.

## Historical event activation and transaction boundary

For a sprint explicitly pinned to `GG-SCORE-STATE-1.0`, submitting a check-in
performs these operations in one database transaction:

1. validate and save the submitted check-in;
2. create and replay-verify its immutable legacy or `GG-TYPED-EVIDENCE-1.0` event;
3. initialize the assessment's current state if needed;
4. process any pending events in submission order;
5. rebuild the current state from the baseline plus every active event;
6. append an immutable score snapshot.

If scoring verification fails, the check-in, evidence event, state update,
and snapshot all roll back. Repeating the operation returns the existing
process snapshot. Database constraints permit only one process transition and
one reversal transition per evidence event.

Drafts have no event. Inconclusive and legacy direction-unknown events receive
a process snapshot and remain in the active audit set, but their contribution
is explicitly withheld and their before/after score states are identical.
Completion and final review create no additional historical evidence event or
historical score transition. This does not apply to the separate
current-version closeout-credit transition described above.

## Snapshots and deterministic replay

Every assessment receives an initialization snapshot. Each processed event,
reversal, and actual repair appends another `ScoreSnapshot`. A snapshot stores:

- contiguous per-assessment sequence;
- operation and algorithm/schema versions;
- the complete 37-lever state before and after the transition;
- decimal values serialized as exact strings;
- the processed event's per-lever contribution, when applicable;
- active event count and a deterministic active-event-set hash;
- hashes of the before and after state;
- an audit reason for reversals.

Snapshots cannot be updated or deleted through the model API. Once an event
has a score snapshot, the protected relationship prevents deleting that
event.

Verification replays every evidence event, contribution, transition, active
event set, need rank, snapshot hash, and final current state. It fails on a
missing event, unsupported version, broken stable link, non-contiguous
history, contribution drift, or current-state drift.

## Rebuild and reversal

Startup runs:

```bash
python manage.py rebuild_score_state
```

after evidence backfill. The command is idempotent: it initializes missing
states, processes pending events once, and appends a rebuild snapshot only
when persisted current state differs from deterministic replay.

Read-only verification is:

```bash
python manage.py rebuild_score_state --verify-only
```

An instance owner may permanently exclude one processed event from current
state while retaining it in the evidence ledger:

```bash
python manage.py rebuild_score_state \
  --reverse-event <event-uuid> \
  --reason "Documented correction reason"
```

The reversal is idempotent and append-only. M3B deliberately does not provide
a user-facing delete or undo-reversal control. Restore a consistent backup if
the wrong event was reversed.

## Missing baseline-mass policy

M3B never invents alpha/beta mass from confidence. A baseline is
`baseline_only` when it has no assessed estimate or no exact/identifiable
mass. It may still appear in the profile and provisional ranking, but evidence
cannot update it.

Canonical Pilot 002 seeding reconstructs 33 identifiable baselines. L06, L15,
L32, and L37 remain `baseline_only`; all four friendship-mapped levers are
active. A future reviewed protocol that maps to an unavailable baseline fails
the submission transaction with an actionable reassessment requirement.
Taking or importing assessment v1.1 produces exact mass for assessed levers
and is the supported upgrade path.

## Historical dynamic provisional need and practice ordering

The richer canonical priority design keeps applicability, importance,
readiness, urgency, and opportunity separate. The M3B production profile path
does not collect or consume them, so it does not invent defaults for them.

Instead, `GG-NEED-RANKING-1.0` deliberately reproduces the existing
assessment v1.1 provisional need function using current estimate `M` and
current confidence `C`:

```text
N = (1 - M)^1.5 × (0.60 + 0.40 × C)
```

Unassessed estimates remain null and sort after assessed needs. Ties break by
stable lever ID. Active protocols are ordered by their canonical parent
competency mapping:

```text
P_t = sum(w_tl × N_l)
```

Weights must sum to approximately 1.0, and recommendation targets must be a
non-empty subset of that mapping. Orientation/archetype style does not alter
ranking. All 383 canonical protocols remain runtime active. This historical
ordering is used only for explicitly legacy-version replay; new
recommendations consume verified composite competency priority.

M6C-03 leaves this state and ordering contract exact. Its separate
`GG-CONTEXT-PRIORITY-1.0` backend result uses the unchanged `P_t` as a base,
requires verified latest assessment/practice context for an explicit epoch,
and withholds incomplete, N/A, or deferred candidates without writing
`LeverState`, `ScoreSnapshot`, recommendation order, sprint, evidence,
completion, or defer records. Ordinary browser recommendations remain the M3B
path until M6C-04 deliberately integrates the reviewed result.

Decision 053 does not change the context multipliers or withholding rules.
It changes only their verified base dependency for a composite assessment
epoch from `GG-NEED-RANKING-1.0` lever priority to
`GG-COMPOSITE-CLOSEOUT-SCORING-1.0` competency remaining priority; the result
hash records which dependency was used.

## Product meaning and exclusions

The current profile labels its inputs as assessment-derived starting
estimates, completion credit, coverage, and remaining priority. A new check-in
cannot move those values by itself. A human closeout may change completion
coverage and practice order, but cannot change:

- the assessment baseline;
- raw self-report;
- orientations or archetypes;
- practice completion state by itself;
- any score of dignity, worth, virtue, or perfection.

Completing a practice does not establish mastery. M6I is deterministic
owner-approved software architecture, not psychometric, clinical, cultural,
accessibility, privacy/safety-specialist, participant, longitudinal, or
intervention-effectiveness validation.
