# Private-pilot feedback contract

## Purpose

M5A collects optional product-usability feedback without treating it as a
developmental observation. The contract is `GG-PILOT-FEEDBACK-1.0`; its
privacy-minimized export schema is
`grounded-growth-private-pilot-export-v1`.

This data answers a narrow product question: can a participant understand and
use the guided experience with acceptable friction? It does not answer whether
a participant has mastered a capacity or whether the assessment or scoring
model is valid.

## Collection boundary

Every feedback record is:

- voluntarily submitted by an authenticated participant;
- append-only after submission;
- stored only in the instance's SQLite database;
- separate from assessment runs, orientation/archetype results, lever
  baselines, lever state, evidence events, score snapshots, sprint state, and
  practice reviews;
- excluded from recommendation and completion services;
- never sent to a remote endpoint.

The application does not automatically time setup or check-ins. Participants
may select a rough time band from memory. No browser analytics, session
recording, tracking pixel, external script, camera, microphone, or remote
telemetry is added.

The form is not an urgent-support channel. Its safety copy tells a participant
to stop an unsafe activity and seek appropriate support instead of relying on
the locally stored form.

## Journey-stage coherence

One feedback record comments on one selected part of the experience.
Practice-specific questions are available only for recommendation, setup,
active-practice, check-in, or review stages. Setup timing is available only
after setup begins; check-in timing is available only for check-in or review.

Local JavaScript progressively hides irrelevant questions. The Django form and
submission service enforce the same rules when JavaScript is unavailable or
bypassed. An out-of-scope answer fails with a participant-facing explanation;
it is never silently discarded.

M5A records created before this rule remain append-only and exportable. M5B
does not rewrite an ambiguous historical record to make it appear cleaner.

## Structured fields

Only journey stage is required to locate the feedback. Submission also
requires at least one optional signal.

| Field | Stable values |
|---|---|
| Journey stage | login, assessment, profile, recommendation, setup, active practice, check-in, review, account, other |
| Protocol | optional canonical `PracticeProtocol.stable_id` |
| Applicability | yes, partly, no, unsure |
| Setup time | under 2 minutes, 2-5 minutes, over 5 minutes, not started |
| Check-in time | under 1 minute, 1-2 minutes, over 2 minutes, not completed |
| Most confusing step | none, login, assessment, profile, recommendation, setup, actions, check-in, review, account, other |
| Accessibility friction | none, present, prefer not to say |
| Safety/boundary friction | none, present, prefer not to say |
| Optional detail | up to 1,000 characters; local only and excluded from export |

The protocol relation exists only to identify the product surface being
discussed. It is not a practice observation and never produces an
`EvidenceEvent`.

## Minimized export

An authenticated participant can download:

```text
/account/pilot-feedback/export.json
```

The same unchanged feedback rows produce the same bytes. Records are ordered
by submission sequence, but the export excludes:

- username or other user identity;
- feedback, user, sprint, check-in, assessment, evidence, and score IDs;
- exact dates and timestamps;
- every free-text comment;
- private person/context labels;
- assessment answers and share codes;
- evidence values, current score state, orientations, and archetypes.

The export retains only contract/schema versions, sequence, stable protocol ID
when selected, categorical answers, and whether optional detail was present.
It explicitly reports that remote telemetry was not used and that the export
did not modify developmental state.

This minimization reduces disclosure; it does not make the file anonymous.
Structured patterns can still be sensitive. Review the JSON before sharing
and store it with access appropriate for private pilot data.

## Retention and deletion

There is no automatic retention timer. Before collecting feedback, the
instance owner should state how long local records and any de-identified
findings will be kept.

Ordinary application use remains append-only. To preview deletion for one
exact local username:

```bash
docker compose exec app python manage.py purge_pilot_feedback \
  --username <username>
```

After confirming the count and the participant-data agreement:

```bash
docker compose exec app python manage.py purge_pilot_feedback \
  --username <username> \
  --confirm
```

The command deletes only that user's optional pilot-feedback rows. It does not
delete assessment, evidence, score, practice, review, orientation, or
archetype state. It does not remove copies already present in SQLite backups;
those backups must be rotated or deleted separately under the same agreement.

## Non-mutation invariant

Submitting, viewing, or exporting feedback must leave these values byte-for-
byte unchanged:

- `AssessmentRun` payloads and share codes;
- `OrientationResult` and `ArchetypeResult`;
- `LeverBaseline`, `LeverState`, and `ScoreSnapshot`;
- `PracticeSprint`, `PracticeCheckIn`, `EvidenceEvent`, and `PracticeReview`;
- recommendation IDs, priorities, and order.

Automated tests snapshot those records and the computed recommendation result
before submission, after submission, and after export. A future request to use
feedback as developmental evidence, applicability input, ranking input, or
score input requires a new reviewed contract and is not compatible with
`GG-PILOT-FEEDBACK-1.0`.
