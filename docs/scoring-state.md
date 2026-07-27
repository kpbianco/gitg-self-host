# M3B score-state activation contract

## Scope

M3B activates the reviewed M3A mathematics for the one complete protocol,
`PRACTICE-FRIENDSHIP-01`. It does not change the assessment scorer, evidence
classifier, canonical task weights, direction semantics, posterior equation,
or confidence equation.

Three versions remain explicit:

```text
GG-SCORING-SHADOW-1.0  posterior and confidence mathematics
GG-SCORE-STATE-1.0     persisted state and transition schema
GG-NEED-RANKING-1.0    provisional need and practice ordering
```

The word `SHADOW` remains in the scoring algorithm ID because M3B activates
the exact reviewed M3A contract instead of silently renaming or
reinterpreting it. The state and ranking layers have their own versions.

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

## Activation and transaction boundary

Submitting a check-in performs these operations in one database transaction:

1. validate and save the submitted check-in;
2. create and replay-verify its immutable `GG-EVIDENCE-1.0` event;
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
Completion and final review create no evidence event and no score transition.

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

## Dynamic provisional need and practice ordering

The richer canonical priority design keeps applicability, importance,
readiness, urgency, and opportunity separate. Those per-user inputs are not
collected yet, so M3B does not invent defaults for them.

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
M3B ranking. Only the friendship protocol is active in canonical production
data; the dynamic ordering path is tested with synthetic competing protocols.

## Product meaning and exclusions

The profile labels current values as provisional evidence estimates.
Submitted evidence can move a current estimate, confidence, need rank, and
practice order. It cannot change:

- the assessment baseline;
- raw self-report;
- orientations or archetypes;
- practice completion state by itself;
- any score of dignity, worth, virtue, or perfection.

Completing this practice does not establish mastery. M3B is software
activation of a reviewed contract, not psychometric validation.
