# M2 evidence contract

## Purpose

M2A turns each submitted practice check-in into one immutable, versioned
`EvidenceEvent`. The event explains the observation's structured detail,
independence, context breadth, repetition, and contradictory direction.

M2B adds read-only ledger, privacy-minimized export, replay verification, and
calibration surfaces around those exact events. This is an event-classification
and audit layer, not dynamic developmental scoring. M2 does not allocate
evidence to levers, calculate task-to-lever coefficients, split
success/failure mass, update a posterior, change confidence, or rerank a
practice.

Algorithm version: `GG-EVIDENCE-1.0`.

## Source and lifecycle

- Draft check-ins are editable working state and have no evidence event.
- Submission requires the M1 observation fields plus three compact choices:
  support used, context comparison, and evidence direction.
- After the first private-pilot session, new submissions also require a real
  attempted action. Before an action occurs, the participant may save a draft
  but cannot create evidence.
- The check-in UI and service accept truthy observation markers only from the
  selected action's reviewed primary/supporting marker set. Markers belonging
  to another action fail with an actionable error rather than being ignored.
- Submission and event creation occur in one database transaction.
- A submitted check-in has exactly one evidence event.
- Both the submitted check-in and event are immutable through model and
  queryset writes.
- The event snapshots every structured input and the exact action-level
  evidence rules needed for deterministic replay. Free-text notes and the
  contents of contradictory evidence are not duplicated into the snapshot.

The M5B submission rules are a prospective input-integrity gate. They do not
change `GG-EVIDENCE-1.0` evaluation, rewrite historical submissions, or make
an older no-attempt event fail replay.

## Protocol-specific observation rules

Evidence rules are seeded on each stable `PracticeAction`. Rules use stable
field names, never display text, and are validated before seed writes.

| Action | Primary markers | Supporting markers |
|---|---|---|
| Listen to what matters now | moved beyond transactional content; meaningful information voluntarily shared | follow-up question; user initiated |
| Make a specific invitation | specific future interaction scheduled | user initiated |
| Follow up | follow-up within seven days; follow-up question | meaningful information shared; user initiated |

These markers describe adherence to the bounded protocol. They do not prove a
broad relational capacity.

## Event dimensions

All stored numeric values use deterministic decimal arithmetic and four
decimal places.

### Protocol performance observation

`p` records only what the submitted fields show about this protocol action:

- `+0.35` when attempted;
- `+0.35` when completed;
- up to `+0.20` from the fraction of primary markers present;
- up to `+0.10` from the fraction of supporting markers present;
- capped at `1.00`.

This is not competency mastery.

### Evidence quality

`q` measures structured specificity, not truthfulness:

- `0.45` for a submitted structured self-report;
- `+0.10` when an actual attempt is recorded;
- `+0.10` when evidence direction is explicitly recorded;
- `+0.05` when support used is recorded;
- `+0.05` when context comparison is recorded;
- `+0.10` when an observable protocol marker or contradictory detail is
  present;
- `+0.05` when expected and observed reciprocity are both recorded;
- capped at `0.85`.

The cap preserves the distinction between one self-report and independent
corroboration. Completion and positive direction do not increase quality:
clear failed or contradictory attempts can be high-quality evidence. Note
length never increases quality.

### Independence

`i` describes support used for the attempt:

| Choice | Factor |
|---|---:|
| Self-directed | 1.00 |
| Reminder or planning aid | 0.85 |
| Real-time prompting or guidance | 0.60 |
| Not recorded in an M1 row | 0.70 |

Independence is not virtue; using support is not treated as a failure.

### Context breadth

`b` is deliberately bounded for a protocol concerning one relationship:

| Choice | Factor |
|---|---:|
| First record in the relationship | 0.55 |
| Similar setting or situation | 0.55 |
| Meaningfully different setting or situation | 0.75 |
| Not recorded in an M1 row | 0.55 |

No friendship event can claim transfer across multiple people. The first
submitted check-in must use `first record`; later submissions must choose
similar or varied context.

### Repetition

`r` is based on submission order for the same stable action within the same
sprint:

| Record for action | Multiplier |
|---|---:|
| First | 1.00 |
| Second | 0.65 |
| Third | 0.40 |
| Fourth and later | 0.25 |

Repetition is action-specific. A first record for another action begins at
`1.00`.

### Contradiction

Direction is stored separately:

| Choice | Contradiction level |
|---|---:|
| Supports expected pattern | 0.00 |
| Mixed or unclear | 0.50 |
| Contradicts expected pattern | 1.00 |
| Not enough happened to tell | 0.00 |
| No structured M1 direction and no text | Unknown |
| Legacy M1 contradiction text present | 0.50 |

Mixed or contradictory new submissions require a brief explanation.
Contradiction does not reduce evidence quality or disappear into a positive
average. A future M3 contract must decide how direction affects
success/failure mass.

## Base evidence mass

The event-level mass is:

`e = q × i × b × r`

It is stored for audit and later algorithm design. It is not distributed
through competency-to-lever weights, and it never writes an assessment
baseline or current score in M2.

## Existing M1 data

Migration adds nullable/blank-compatible metadata fields without rewriting an
existing check-in. After canonical seeding, startup runs:

```bash
python manage.py backfill_evidence_events
```

The command processes submitted M1 rows in stable submission order, uses
conservative `not recorded` factors, preserves unknown contradiction as
unknown, and creates missing events. It is idempotent. Existing events are
replayed from their snapshots and rejected if stored outputs do not match.

Use `--dry-run` to inspect the number of missing events.

## User presentation

Submitted history shows a plain-language event reading. The detail page
explains direction, structured detail, support, context, and repetition. M2B
adds one authenticated, paginated ledger across the user's practices, with
plain-language direction filtering and no private context or note text.
Numeric internals and the algorithm version are available only in a collapsed
technical audit section.

Every evidence page states that one observation does not establish mastery.
Under M3B, it also explains that eligible directional evidence may contribute
to the separate current working profile while inconclusive or unknown
direction is withheld.

## M2B audit boundary

The `grounded-growth-evidence-export-v1` JSON export is deterministic and built
by allowlist. It preserves stable protocol/action IDs, event order, structured
inputs, snapshotted rules, and stored outputs while excluding user and record
IDs, exact timestamps, private context labels, all free text, assessment
answers, and share codes.

`verify_evidence_events` is read-only and fails on a missing event, an extra
event, incorrect repetition order, stable-ID mismatch, malformed snapshot, or
any replay drift. Direction-complete synthetic fixtures live under
`tests/fixtures/evidence/`.

The detailed privacy, operational, and calibration contract is in
`docs/evidence-audit.md`.

## Explicit M2 exclusions

- no `k_tl` task-to-lever coefficient;
- no lever evidence/success/failure contributions;
- no evidence mass added to a `LeverBaseline`;
- no mastery or confidence mutation;
- no score snapshot because no score state changes;
- no task-priority or recommendation update;
- no archetype or orientation update;
- no inference from free-text note length or sentiment;
- no claim that self-report is independently verified.
