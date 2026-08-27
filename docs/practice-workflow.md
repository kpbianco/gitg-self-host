# Practice workflow

## Current M6F workflow

All 383 canonical protocols are available and score active. The five original
protocols use the legacy compact Boolean/scale check-in vocabulary; the other
378 render action-specific typed fields for explicit observation state,
provenance, and Boolean, count, frequency, ordinal, duration, objective,
artifact-criteria, conceptual-criteria, scenario-criteria, or attestation
values as required by each action.

Submission persists the check-in, creates and replay-verifies either a legacy
or typed evidence event, projects it through the protocol's canonical parent
competency mapping, updates the separate current working lever state, and
appends an immutable score snapshot in one transaction. Ineligible or withheld
evidence receives an auditable transition without a score contribution. Notes,
private labels, and artifact contents are not score inputs.

The milestone sections below describe how the workflow evolved; their former
friendship-only and score-inactive boundaries are historical.

## Implemented protocol

M1 activates one protocol: **Deepen One Existing Friendship**. It runs for 14
days and provides three fixed actions:

1. initiate a substantive conversation and spend at least ten minutes
   primarily listening;
2. propose a specific shared activity and date;
3. follow up within seven days on something the person shared.

The user does not design the intervention. M4A also activates
**Schedule Non-Instrumental Play**, a 10-day protocol with three fixed actions:
reserve a play window, engage without an output goal, and return once within
seven days. M4B activates **Practice Emotional Cue Detection**, a 10-day
protocol that separates observation from interpretation, holds multiple
hypotheses, and checks an impression with a neutral question. M4C activates
**State and Maintain One Boundary**, a 10-day protocol that defines a
self-directed limit, states it directly, and follows through once. M4D
activates **Complete an Attention-Presence Experiment**, a 10-day protocol
that compares one usual and one changed 15-minute condition, then repeats the
more workable condition. All five seeded protocols are executable.

## Guided setup

The seven server-rendered steps cover:

1. why the current provisional profile produced this recommendation;
2. whether the protocol is currently applicable;
3. a minimal private label for one person or context;
4. protocol-specific privacy, safety, access, and interpersonal boundaries;
5. a start date within two weeks;
6. review of the exact three actions;
7. final summary and activation.

Setup state is kept in the authenticated session until activation. The
database records when setup and boundary acknowledgement complete.

## Sprint states

One database constraint permits at most one active or paused sprint per user.
The allowed transitions are:

| Current | Allowed next state |
|---|---|
| Active | Paused or stopped |
| Paused | Active or stopped |
| Stopped | Terminal |
| Completed | Terminal |

Stopping is final. Pausing is reversible and does not request evidence while
paused. State transitions use POST with CSRF protection and are implemented in
the domain service, not in templates.

## Compact check-ins

A check-in is tied to a stable practice-action ID and displays a
protocol-configured subset of the reviewed fields:

- attempted/completed;
- user initiation and movement beyond transactional content;
- follow-up question and voluntarily shared meaningful information;
- scheduled future interaction and seven-day follow-up;
- internal resistance, expected reciprocity, and observed reciprocity;
- contradictory evidence and an optional minimal note.

A draft has no submission timestamp, is editable, does not appear in submitted
history, and does not count toward completion. Submission adds a timestamp and
makes the check-in immutable. In M2A, submission also requires three compact
choices: support used, context comparison, and evidence direction.

Submission and `GG-EVIDENCE-1.0` event creation occur in one transaction. The
event is immutable and replayable from its structured snapshot. The submitted
history links to a plain-language evidence reading; technical values remain in
a collapsed audit section. M2B adds a private cross-practice ledger and
minimized calibration export without exposing draft or free-text content.

Starting in M3B, submission also processed eligible events against a canonical
mapping and appended an immutable score snapshot in that same transaction.
Drafts create neither event nor snapshot. Inconclusive observations receive an
auditable process transition but do not move current state.

## Completion and review

The service derives completion evidence from submitted check-ins only:

- all three stable action IDs have an attempt;
- at least two distinct actions are completed;
- the protocol's configured completion markers are present, using its reviewed
  `any` or `all` marker mode;
- a final review is submitted.

The review and sprint completion are written in one transaction. The review
stores the derived counts, reflection, contradictory evidence, an empty static
impact preview, and the required disclaimer:

> Completing this practice does not establish mastery.

No assessment baseline, orientation, or archetype row is updated. The final
review creates no score event or snapshot; eligible check-ins were processed
at submission time. Tests compare current state immediately before and after
completion to prove that completion alone has no effect.

## Evidence and scoring boundary

M1 records protocol participation, not validated behavior change. M2A adds
versioned event-level quality, independence, bounded context breadth,
action-specific repetition, contradiction, protocol performance, and base
evidence mass.

M2B adds ledger, export, replay-verification, and synthetic calibration
surfaces around those immutable events. M2 still does not distribute evidence
through competency-to-lever mappings, calculate success/failure contributions,
mutate mastery/confidence/need, or change recommendations. See
`docs/evidence-contract.md` and `docs/evidence-audit.md`.

M3A reviewed the task allocation and posterior contract. M3B first activated
that contract for friendship; M6F extends the same separate-current-state
architecture to all canonical protocols and recalculates provisional
recommendation order.
See `docs/scoring-shadow.md` and `docs/scoring-state.md`.

M4A makes protocol setup copy, compact observation labels, and completion
markers data-driven. The play protocol creates immutable evidence, but its
explicit `score_active=false` boundary means submission creates no score
snapshot and cannot change current lever state or recommendation order.

M4B reuses that configuration for emotional cue detection. Its safety boundary
is substantive: nonverbal cues are uncertain and culturally contextual, and
direct clarification is required before completion. It also remains
`score_active=false`.

M4C uses the same evidence vocabulary but requires both configured markers:
one direct boundary statement and one proportionate follow-through or
restatement within seven days. It distinguishes a boundary from threats,
punishment, silent tests, or forced agreement and excludes contexts with
abuse, coercive control, unsafe dependency, or likely retaliation. It remains
`score_active=false`.

M4D also uses the all-marker completion mode. It requires a usual-versus-changed
condition comparison and one repeat within seven days. Its 15-minute windows
measure noticing and returning attention rather than output or distraction
counts. Movement, fidgets, assistive technology, reminders, and necessary
alerts remain valid supports; safety-critical contexts and surveillance are
excluded. It remains `score_active=false`.
