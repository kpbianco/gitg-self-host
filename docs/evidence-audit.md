# M2B evidence audit and calibration

## Scope

M2B makes the immutable `GG-EVIDENCE-1.0` events reviewable, exportable for
calibration, and verifiable as a complete database history. It does not change
the M2A evidence mathematics or write any developmental profile value.

M2B adds:

- an authenticated, user-scoped evidence ledger;
- a deterministic privacy-minimized JSON export;
- strict read-only replay verification;
- versioned synthetic golden calibration cases.

There is no migration in M2B. Existing evidence rows remain unchanged.

## Authenticated ledger

`/evidence/` shows only events whose submitted check-in belongs to the signed-in
user. It uses plain-language action, direction, evidence-strength, support, and
repetition labels. Exact event coefficients remain on the existing collapsed
technical audit section of the individual evidence-reading page.

The ledger:

- includes submitted check-ins with an evidence event;
- excludes drafts;
- defaults to newest first;
- paginates at 20 events;
- filters by supportive, mixed, contradictory, inconclusive, or not-recorded
  direction;
- verifies complete event coverage, repetition order, and exact replay before
  rendering; no partial ledger is shown on integrity failure;
- is marked private and non-cacheable;
- shows no person/context label, note, or contradiction-detail text;
- explicitly states that the developmental profile is unchanged.

The full private note remains available only on the user-scoped individual
evidence-reading page.

## Privacy-minimized export

The authenticated download endpoint is:

```text
/evidence/export.json
```

Schema version:

```text
grounded-growth-evidence-export-v1
```

The export is built by explicit allowlist. Each event contains:

- a sequential position, oldest first;
- evidence algorithm version;
- stable protocol and action IDs;
- structured attempt, observation, resistance, reciprocity, support, context,
  direction, text-presence, repetition, and versioned action-rule values;
- stored event outputs as four-decimal strings.

It deliberately excludes:

- username, user ID, or email;
- evidence-event, practice-sprint, and check-in IDs;
- exact dates or times;
- person or context labels;
- note text and contradiction-detail text;
- assessment answers and clarifier answers;
- assessment share codes.

The sequence is retained because repetition order is part of the evidence
contract. No export-generation timestamp is added, so identical stored records
produce identical bytes. Responses are marked private and non-cacheable.

This is a privacy-minimized calibration artifact, not an anonymous public-data
guarantee. Structured behavioral values can still be sensitive. Review the
file before sharing it and transfer it through an appropriately protected
channel.

## Replay verification

Run:

```bash
make evidence-verify
```

Inside the deployed container:

```bash
docker compose exec app python manage.py verify_evidence_events
```

The command performs no writes. It:

1. walks every submitted check-in in stable sprint/action/submission order;
2. requires exactly one evidence event for each submission;
3. requires the stored repetition index to match that order;
4. replays the exact snapshotted input and action rules;
5. compares the algorithm version, stable IDs, structured snapshot, every
   numeric output, and explanations;
6. fails if the event count and submitted-check-in count differ.

Any gap or drift exits nonzero with an actionable identifier. The command does
not repair data. `backfill_evidence_events` remains the separately explicit,
idempotent startup reconciliation path.

## Calibration fixtures

`tests/fixtures/evidence/calibration_v1.json` locks synthetic examples for:

- supportive evidence;
- inconclusive evidence;
- mixed evidence;
- contradictory evidence;
- conservative legacy M1 evidence with direction not recorded.

The cases cover different support, context, repetition, performance, and
contradiction combinations. They contain no real person or pilot narrative.
They are golden software fixtures, not psychometric validation. A future
algorithm must add a newly versioned fixture set instead of silently replacing
these expected outputs.

## Static-profile boundary

Ledger views, export, and replay verification are read-only. Tests snapshot all
37 Pilot 002 lever baselines before and after these operations. M2B does not:

- allocate event mass to levers;
- calculate success or failure contributions;
- update mastery, confidence, evidence mass, need, or task priority;
- change archetypes or orientations;
- rerank recommendations;
- create score snapshots.

M3 remains a separate design and review gate.
