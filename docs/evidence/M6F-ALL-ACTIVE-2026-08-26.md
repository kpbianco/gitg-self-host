# M6F all-catalog runtime and score activation evidence

Date: 2026-08-26  
Batch: `M6F-ALL-ACTIVE`  
Decision: `docs/PRODUCT_DECISIONS.md#decision-052--activate-the-complete-canonical-protocol-catalog`  
Baseline: `c0fcabde4ce71a616b1c90d604e521b8d76146e5`

## Outcome

The complete canonical competency catalog is runtime available and production
score active under the owner-directed M6F software boundary. Activation is
exact rather than sampled or lower-bounded.

| Contract surface | Verified value |
| --- | ---: |
| Canonical competencies | 383 |
| Canonical protocol packages | 383 |
| Runtime-active protocols | 383 |
| Score-active protocols | 383 |
| Practice actions | 1,151 |
| Typed-v2 runtime and score-active protocols | 378 |
| Legacy-v1 runtime and score-active protocols | 5 |
| Canonical competency-to-lever links | 1,403 |
| Uncovered or explicitly unauthored competencies | 0 |

All protocols use `SP-STRUCTURED-EVIDENCE-ELIGIBLE`. The five frozen legacy
protocols retain `practice-observation-v1`; the other 378 protocols use
`GG-TYPED-EVIDENCE-1.0` with action-specific structured measurement rules.

## Implemented contract

- Every canonical competency has exactly one stable-ID-addressable protocol,
  complete activation-ledger coverage, at least one action, typed or legacy
  evidence rules, recommendation targets, and a complete canonical
  parent-competency score mapping.
- Typed check-ins persist explicit observation state, provenance, measurement
  kind, and allowlisted structured values. Free text and artifact contents are
  not score inputs.
- Eligible evidence contributes once through the complete canonical parent
  mapping. Recommendation-target subsets do not replace scoring allocation.
- Score state is derived separately from immutable assessment baselines and is
  deterministic, atomic, idempotent, replayable, reversible, rebuildable, and
  hash audited across shared-lever contributions.
- Unknown, not-applicable, deferred, unattempted, stale, adverse, unobserved,
  inconclusive, and contract-invalid observations remain visible but are
  withheld from score mass without penalty.
- The practice library exposes all 383 active protocols. Browser coverage
  asserts the exact catalog count and walks representative legacy and typed
  protocols without attempting a 383-card full-page screenshot.

## Deterministic source state

| Artifact | Value |
| --- | --- |
| Practice catalog content hash | `4f7de352e79214bb2c923e7c6b6281100844141f2e7b2bfc0c5d320b4aa8d594` |
| Frozen five-protocol legacy projection hash | `9eff5558607936aab20ec2adcdf4912510e9f8816cc291ae6b77918bf6711672` |
| Production score eligibility | `GG-PRODUCTION-SCORE-ELIGIBILITY-2.0` |
| Score state | `GG-SCORE-STATE-1.0` |
| Typed evidence | `GG-TYPED-EVIDENCE-1.0` |

## Local verification

The following results were obtained from the M6F candidate worktree:

| Verification | Result |
| --- | --- |
| `.venv/bin/pytest -q -m "not e2e"` | PASS — 351 passed, 11 deselected in 36m35s |
| `./scripts/agent-verify.sh full` | PASS — all cumulative contract, quick, and full gates; 351 tests passed in its 37m57s quick phase |
| Migration rollback data-preservation test | PASS — pre-existing rows preserved across 0010 rollback/reapply |
| Ruff format and lint | PASS — 200 files; no diagnostics |
| Django system check | PASS — no issues |
| Migration drift check | PASS — no changes detected |
| `make full-frontier-check` | PASS — deterministic and current, 383/383 |
| Practice and competency-evidence report checks | PASS — current |
| Pilot readiness | PASS — 383 active, 1,151 actions, 383 score-active |
| Curriculum expansion readiness | PASS — 383 runtime, 383 score-active, 5 legacy-compatible projections |
| Competency-evidence readiness | PASS — 378 typed production/score-active, 383 total score-active |
| Context-priority readiness | PASS — 383 projected, 383 score-active |
| Context, Personal OS, M6C, and M6D readiness | PASS |
| Playwright collection | PASS — all 11 browser journeys collected |
| Local Compose deployment drill | NOT STARTED — `docker` executable unavailable |

Local browser execution could not start because no Chromium executable was
present and the environment returned a zero-byte archive for every official
Playwright CDN retry. This is an environment dependency failure, not a test
failure. The hosted `browser` job installs Chromium and remains required before
the candidate can be reported as fully verified.

Local Compose execution also could not start because this environment does not
provide the `docker` command. The hosted `compose` job runs the required
deployment, backup, recreation, restore, and verification drill.

The hosted `quality`, `browser`, `compose`, and aggregate `pilot-ready` jobs are
also required. Their run IDs and results are reported on the pull request after
the immutable candidate commit is published.

## Audit and claim boundary

Decision 052 authorizes software activation before the consolidated content
audit; it does not fabricate completion of that audit. Semantic, source,
originality, accessibility, privacy, safety, specialist, cultural,
psychometric, clinical, participant, longitudinal, and intervention-
effectiveness review remain pending for the owner's audit. No completion or
score establishes mastery, identity, dignity, clinical status, professional
qualification, or human worth.
