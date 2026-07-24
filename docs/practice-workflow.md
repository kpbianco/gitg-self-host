# Practice workflow

## Implemented protocol

M1 activates one protocol: **Deepen One Existing Friendship**. It runs for 14
days and provides three fixed actions:

1. initiate a substantive conversation and spend at least ten minutes
   primarily listening;
2. propose a specific shared activity and date;
3. follow up within seven days on something the person shared.

The user does not design the intervention. Four other protocols remain
inactive structured placeholders.

## Guided setup

The seven server-rendered steps cover:

1. why the static profile produced this recommendation;
2. whether the relationship is currently applicable;
3. a minimal private label for one person or context;
4. privacy, welcome contact, disclosure, autonomy, and reciprocity boundaries;
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

A check-in is tied to a stable practice-action ID and captures only the M1
protocol fields:

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
a collapsed audit section.

## Completion and review

The service derives completion evidence from submitted check-ins only:

- all three stable action IDs have an attempt;
- at least two distinct actions are completed;
- at least one attempted interaction moved beyond transactional content or
  involved voluntarily shared meaningful information;
- a final review is submitted.

The review and sprint completion are written in one transaction. The review
stores the derived counts, reflection, contradictory evidence, an empty static
impact preview, and the required disclaimer:

> Completing this practice does not establish mastery.

No assessment or lever row is updated. Tests snapshot every raw, calibrated,
confidence, need, and rank value before completion and compare it afterward.

## M2A boundary

M1 records protocol participation, not validated behavior change. M2A adds
versioned event-level quality, independence, bounded context breadth,
action-specific repetition, contradiction, protocol performance, and base
evidence mass.

M2A still does not distribute evidence through competency-to-lever mappings,
calculate success/failure contributions, mutate mastery/confidence/need, or
change recommendations. See `docs/evidence-contract.md`.
