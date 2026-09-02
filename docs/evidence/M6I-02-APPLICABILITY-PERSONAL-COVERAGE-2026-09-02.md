# M6I-02 applicability and personal coverage evidence

Date: 2026-09-02
Baseline: `d7b07e732cee34bffdb1e9c64520573e92d85414`
Branch: `codex/m6i-02-applicability-personal-coverage`

## Implemented boundary

- Decision 054, ADR 0014, and
  `GG-PERSONAL-APPLICABLE-COVERAGE-1.0` define a read-only current-assessment
  projection.
- A direct authenticated recommendation action records explicit N/A through
  the existing immutable `PracticeContext` service and opens the distinct-
  alternative route.
- Latest verified N/A excludes only the active protocol's parent competency
  from the personal denominator. The UI shows that denominator, the exclusion
  count, and unchanged canonical coverage together.
- No migration or new persisted sensitive field was added.

## Local verification

- Ruff lint and format: passed.
- Django system check and migration drift: passed; no changes detected.
- Focused applicability suite: 5 passed.
- Applicability plus existing Personal OS/context suite: 23 passed.
- Existing profile-focused shadow tests: 5 passed, 7 deselected.
- Isolated applicability readiness migration/seed/replay gate: passed with 383
  canonical competencies and unchanged canonical state.
- Practice reports, governance audit, composite catalog, competency-evidence
  reports, and full-frontier deterministic checks: passed.
- Agent contract: passed; manifest contained 849 files at that checkpoint.
- Agent quick: 403 passed, 13 hosted-browser tests deselected in 1,957.37
  seconds.

## Hosted verification

Pending draft PR publication. Required jobs are Ruff/Django/pytest/readiness,
Playwright core journeys, Docker Compose deployment drill, and aggregate Pilot
readiness.

## Claim boundary

This evidence supports deterministic software, replay, isolation, and ordinary
UX behavior only. `ER-M6A-003` remains pending, `RG-M6A-002` remains open, and
M6B specialist acceptance remains false. It does not claim formal source
completeness or specialist, accessibility, privacy/safety, psychometric,
cultural, participant, longitudinal, release, deployment, mastery, or
intervention-effectiveness acceptance.
