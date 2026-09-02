# Current state

Last updated: 2026-09-02
Implementation branch: `codex/m6i-02-applicability-personal-coverage`
Baseline: `d7b07e732cee34bffdb1e9c64520573e92d85414`

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

## Verification

The bounded M6I-02 gate is:

```bash
make applicability-coverage-check PYTHON=.venv/bin/python
.venv/bin/python -m pytest tests/test_applicability_coverage.py tests/test_personal_os_browser.py
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
