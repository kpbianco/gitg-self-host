# Current state

Last updated: 2026-09-05
Implementation branch: `codex/m6j-02-self-knowledge`
Baseline: `e993ad142dee7652c3c029d6b1c75c0cdaf3d298` (merged PR #52)

## Current M6J content delivery

M6J-02 adds 12 individually authored self-knowledge practices (05.01–05.12)
and 36 tailored actions. There are now 54 authored practices and 329 still
rewrite-pending. The 42 earlier practices, all stable IDs and activation,
assessment, ranking, scoring and human-closeout behavior remain unchanged.
Coverage is not specialist acceptance or empirical validation. The branch's
exact verification and publication results belong in its M6J-02 evidence
record and PR; the earlier M6I implementation history below remains relevant.

PR #52 merged on 2026-09-05 at 16:07:55 UTC. Its PR quality and Compose jobs
were cancelled and its aggregate failed; that PR run is not passing evidence.
A separate main run, 33976905386, began at the merge and was still running
when this continuation began. It must be assessed on its own results.

## Canonical runtime and scoring

- The catalog contains exactly 7 families, 37 levers, 27 domains, 383
  competencies/practices, 1,151 actions, and 1,403 competency-lever
  relationships. All 383 protocols are runtime available under Decision 052.
- Decision 053 prospectively replaces event-level score mutation for new
  sprints with `GG-COMPOSITE-CLOSEOUT-SCORING-1.0`.
- The concise assessment initializes priority; it neither awards completion
  credit nor directly measures all 383 competencies.
- Check-ins are immutable evidence only. Composite state changes only after an
  explicit final human closeout: the configured minimum earns 0.75 and every
  action earns 1.00. Repeats use maximum active credit, never a sum.
- Historical `GG-SCORE-STATE-1.0`, assessment data, evidence events, and score
  snapshots remain immutable and replayable. Completion is not mastery.

## M6I-02 applicability and personal coverage

- Decision 054 and ADR 0014 define
  `GG-PERSONAL-APPLICABLE-COVERAGE-1.0` as a read-only projection.
- An active recommendation has a direct, CSRF-protected “not applicable to me”
  action. It records the existing immutable current-epoch `PracticeContext`
  state and opens the distinct-alternative flow.
- Only a latest verified explicit N/A removes the protocol's parent competency
  from the separately labeled personal-applicable denominator. Unknown,
  deferred, provided, and explicit zero remain distinct.
- The profile shows personal coverage, included count, excluded count, and
  unchanged canonical coverage together. An empty personal denominator is
  unavailable, not 100 percent.
- Context input awards no credit and does not change composite state, state
  hashes, snapshots, canonical coverage, recommendation mathematics, or legacy
  replay. Reassessment begins with a fresh denominator.
- Invalid owner, epoch, revision, snapshot, or hash data fails only the personal
  projection closed; verified canonical coverage remains visible.

## M6I-03 assessment calibration readiness

- Decision 055 and ADR 0015 define
  `GG-ASSESSMENT-CALIBRATION-READINESS-1.0` as a deterministic source-only
  audit.
- The audit freezes exact hashes for the assessment v1.1 spec, model, browser
  scorer, and coverage artifact and recomputes the complete item-to-lever
  coverage inventory.
- The structural inventory contains 50 core items, 37 capability clarifiers,
  six orientation clarifiers, 37 levers, seven families, and six orientations.
  Every lever has one direct core item and one adaptive clarifier.
- Eight empirical evidence axes remain `data_collection_required`; none is
  represented as complete. The report does not read runtime assessment runs or
  any participant or owner-private data.
- This batch changes no assessment source, scoring constant, database, UI,
  recommendation, completion, evidence, or replay behavior.

## M6I-04 consented assessment calibration data

- ADR 0016 and the consent contract define explicit per-run permission for secondary
  calibration use of an already-stored participant-created assessment.
- Enrollment is off by default. The Pilot 002 seed is ineligible. Consent,
  withdrawal, and reconsent are append-only, current-state controlled, and
  deterministic.
- A random pseudonymous token links only explicitly included retakes. The
  dataset excludes identity, exact timestamps, assessment IDs, share codes,
  free text, private context, developmental history, and derived profile
  outputs.
- The owner can inspect their exact contribution. Operator export requires an
  explicit sensitive-data acknowledgement, creates a new mode-0600 file,
  refuses overwrite, and performs no upload.
- Consent is covered by owner archive, deletion, backup/restore, readiness, and
  reversible migration. Withdrawal does not alter the private assessment.
- Software collection capability contributes no participant sample and closes
  zero of the eight empirical evidence axes. Completed runs do not measure
  abandonment.

## M6I-05 assessment calibration analysis readiness

- ADR 0017 defines
  `GG-ASSESSMENT-CALIBRATION-ANALYSIS-READINESS-1.0` as a local-only analyzer
  for an exact, hash-verified M6I-04 export.
- The analyzer reads no live database, makes no network call or upload, and
  emits no participant rows, pseudonyms, raw responses, raw timing, identity,
  exact timestamps, share codes, free text, private context, developmental
  history, or derived profile output.
- Its deterministic private aggregate contains exact cohort/source totals,
  response and timing summaries with nonzero cells below five suppressed,
  allowlisted response-quality summaries, workflow-threshold status, and
  explicit per-axis limitations.
- Thirty consented participants and thirty linked-retest participants are
  software workflow thresholds only. Exploratory consecutive-pair agreement
  is not a reliability conclusion.
- External reference measures, population-group variables, abandoned
  attempts, participant fit judgments, and longitudinal outcomes remain
  missing. Completed-run timing cannot measure abandonment.
- All eight participant evidence axes remain incomplete and not established;
  `completed_axes` remains zero even when a threshold is met.
- Operator analysis requires explicit acknowledgement, creates a new mode-0600
  file, refuses overwrite, and leaves consent, collection, assessment, score,
  recommendation, evidence, completion, UI, migrations, and replay unchanged.

## Verification

The bounded M6I-05 gate is:

```bash
make assessment-calibration-check PYTHON=.venv/bin/python
make assessment-calibration-collection-check PYTHON=.venv/bin/python
make assessment-calibration-analysis-check PYTHON=.venv/bin/python
.venv/bin/python -m pytest tests/test_assessment_calibration_analysis.py tests/test_assessment_calibration_consent.py tests/test_deployment_contract.py
./scripts/agent-verify.sh contract
./scripts/agent-verify.sh quick
```

Hosted verification must also pass the Playwright core journeys and the Docker
Compose deployment drill. Local Chromium and Docker availability do not replace
those hosted gates.

## Open non-software gates

- `ER-M6A-003` remains pending and `RG-M6A-002` remains open.
- M6B specialist acceptance remains false.
- The M6B audit retains 3,369 review signals: 1,045 high, 2,073 moderate, and
  251 low. Formal claim-level source completeness is unfinished for all 383
  packages.
- Specialist, accessibility, privacy/safety, psychometric, cultural,
  participant, longitudinal, release, deployment, mastery, and intervention-
  effectiveness acceptance must not be fabricated. Required changes become
  versioned follow-on scope rather than rewritten historical evidence.
