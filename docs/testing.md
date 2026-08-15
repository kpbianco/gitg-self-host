# Testing

## Development setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" \
  .venv/bin/python -m playwright install chromium
```

Node.js is used only to execute the canonical assessment JavaScript in golden
tests. It is not a deployed server or runtime dependency.

Each pytest invocation uses a unique SQLite database under the system
temporary directory. This prevents a completed WAL-enabled process from
leaving sidecars that can collide with a subsequent unit or browser run.

## Commands

```bash
make format
make lint
make test
make pilot-check
make practice-report-check
make curriculum-check
make competency-evidence-check
make context-check
make personal-os-check
make context-priority-check
make m6c-pilot-check
make m6d-01-check
make e2e
make compose-smoke
```

`make lint` runs Ruff format/lint checks and Django's system check.

`make pilot-check` creates a temporary data directory, applies every
migration, creates the one-time bootstrap user, seeds twice, reconciles
evidence and score state, and then runs the read-only
`GG-PILOT-READINESS-1.0` verifier. It removes its isolated database on exit
and never touches `./var`, `.env`, or the deployed volume.

`make practice-report-check` recomputes the 383-row coverage ledger, domain
and lever matrices, risk register, summary, and originality report as exact
bytes. It fails on missing or stale committed output.

`make curriculum-check` creates another disposable database, validates the
manifest-listed practice release, seeds twice, reconciles evidence and score
state, invokes the unchanged pilot verifier through the additive
`GG-CURRICULUM-EXPANSION-READINESS-1.0` contract, and compares the canonical
projection with the seeded runtime.

`make competency-evidence-check` runs additive
`GG-COMPETENCY-EVIDENCE-READINESS-1.0`. It verifies exact v1 replay,
fail-closed typed dispatch, golden typed evidence and shadow projections,
property/invariant coverage, deterministic reports, and unchanged production
state. A pass means software-ready, not M6B-accepted:
`ER-M6A-003` and `RG-M6A-002` remain external governance blockers.

The M6B report set is:

- `reports/practice-content/typed_evidence_capability_v1.csv`;
- `reports/practice-content/scoring_policy_execution_v1.csv`;
- `reports/practice-content/competency_evidence_readiness_v1.json`.

The readiness JSON must distinguish software readiness from specialist review,
record zero typed production protocols and zero typed score-active protocols,
and keep M6B acceptance false while `ER-M6A-003` is pending.

`make context-check`, `make personal-os-check`, and
`make context-priority-check` independently exercise the M6C-01 through
M6C-03 contracts from isolated state. `make m6c-pilot-check` is an additive
isolated drill for read-only `GG-M6C-PILOT-READINESS-1.0`; it invokes all six
prerequisite readiness contracts, checks exact definition IDs, five active
canonical protocols, friendship-only activation, authenticated route
registration, and empty or valid optional state, and must not print private
authored values or write database state.

`make test` covers:

- canonical counts, IDs, mapping coverage, and weights;
- malformed mapping rejection;
- idempotent curriculum, protocol, and Pilot 002 seeding;
- offline JSON Schema validation for protocol packages and every practice
  registry;
- manifest path safety, exact package enumeration, content hashing, stable-ID
  uniqueness, and cross-reference rejection;
- exact five-protocol runtime projection parity with the post-M4 fingerprint;
- canonical parent/domain and recommendation-target-subset validation before
  writes;
- deterministic 383-row coverage deriving the current source frontier while
  preserving five projected runtime packages,
  27-domain and 37-lever matrices, and explicit risk/scoring/activation state;
- exact/normalized/near-duplicate, reflection, action-shape, duration,
  evidence-rule, and known Notion journal-prompt originality reporting;
- additive, read-only expansion readiness while the independent
  `GG-PILOT-READINESS-1.0` contract remains callable;
- exact `GG-EVIDENCE-1.0` replay through version dispatch and fail-closed
  unknown event/rule versions;
- `GG-TYPED-EVIDENCE-1.0` fixtures for Boolean, count/frequency, ordinal,
  duration, artifact, conceptual/scenario, objective, consented-observer,
  qualified-attestation, unknown/not-observed, contradiction, and adversity;
- explicit rule normalization with no inferred “more is better” semantics and
  no free-text score input;
- evidence-only `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` unknown baseline,
  typed withholding, replay, and reversal;
- one-way `GG-COMPETENCY-LEVER-SHADOW-1.0` full-mapping validation,
  duplicate-event rejection, input-order independence, no double counting,
  and no lever-to-competency feedback;
- separate `GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` with every new M6B typed
  path production-ineligible;
- `GG-COMPETENCY-EVIDENCE-READINESS-1.0` proving no assessment baseline,
  current lever state, score snapshot, recommendation, or activation change;
- one-time bootstrap user behavior and password-hash preservation;
- login enforcement, CSRF-bearing login, and public health;
- authenticated home/profile/assessment/practice rendering;
- immutable and idempotent assessment-run persistence;
- exact 6-orientation, 15-archetype, and 37-lever golden-result persistence;
- exact canonical alpha/beta baseline-mass persistence and drift rejection;
- GGA11 answer/code agreement and malformed assessment rejection;
- the seven-step practice setup and not-applicable exit;
- one-current-practice and per-user authorization boundaries;
- draft/submitted check-in separation and submitted immutability;
- prospective evidence submission requiring an actual attempted action;
- action-specific observation prompts and rejection of markers belonging to
  another action;
- required M2 evidence metadata on submission;
- deterministic `GG-EVIDENCE-1.0` output and exact replay;
- action-specific repetition and bounded context semantics;
- structured and legacy contradiction handling;
- atomic event creation, event immutability, and privacy-minimized snapshots;
- conservative, idempotent M1 evidence backfill;
- direction-complete synthetic calibration fixtures and exact golden outputs;
- authenticated, filtered, per-user evidence-ledger isolation;
- deterministic allowlisted export with identity, IDs, timestamps, free text,
  and assessment data excluded;
- strict whole-database replay verification and nonzero failure on gaps/drift;
- unchanged lever baselines after ledger, export, and verification operations;
- stable `17.03` practice mapping and four task weights summing to 1.0;
- exact `GG-SCORING-SHADOW-1.0` coefficients, direction routing,
  success/failure mass, posterior, and confidence against a synthetic fixture;
- monotonic confidence for included evidence and unchanged confidence for
  withheld evidence;
- malformed task weights, duplicate events, and ambiguous baseline mass
  failing closed;
- draft exclusion and unchanged stored profile state after shadow projection;
- exact assessment v1.1 provisional-need reproduction across all 37 baseline
  rows;
- separate 37-row current-state initialization and four conservative Pilot
  baseline-only rows;
- atomic and idempotent submitted-event application with unchanged assessment
  baselines;
- withheld inconclusive state, immutable contribution snapshots, and
  protected scored events;
- full score-history hash/replay verification, audited event reversal, and
  deterministic drift repair;
- missing required baseline mass rolling back check-in, event, state, and
  snapshot together;
- dynamic active-protocol ordering from current need and canonical weights;
- complete play, emotional-cue, boundary, and attention-presence protocol
  configuration;
- exact `GG-PILOT-READINESS-1.0` source/database/protocol/Pilot 002 inventory;
- read-only readiness verification and fail-closed score-activation,
  profile-completeness, and availability drift behavior;
- protocol-specific compact check-in fields and boundary language;
- immutable evidence with zero score snapshots or lever-state movement for
  score-inactive protocols;
- direct clarification required for emotional-cue completion;
- both a direct statement and follow-through required for boundary completion;
- both a condition comparison and repeat required for attention-presence
  completion;
- score-state management-command verify and repair behavior;
- pause/resume/stop transitions and completion criteria;
- unchanged assessment baselines and no review-only current-state transition;
- SQLite foreign keys, busy timeout, and WAL;
- consistent backup and SQLite integrity;
- assessment v1.1 complete golden output, GGA11, and GGA1;
- authenticated optional pilot-feedback submission and per-user isolation;
- journey-stage-specific feedback questions with matching no-JavaScript
  server enforcement;
- append-only `GG-PILOT-FEEDBACK-1.0` persistence and fail-closed export
  validation;
- deterministic `grounded-growth-private-pilot-export-v1` output with
  identity, IDs, timestamps, free text, private context, assessment, evidence,
  score, orientation, and archetype data excluded;
- unchanged assessment, evidence, lever state, snapshots, sprint, check-in,
  review, orientation, archetype, recommendation priorities, and
  recommendation order after feedback submission and export.
- preview-first, exact-user pilot-feedback deletion with other users and all
  developmental state unchanged;
- exact authenticated Personal OS staging, latest-assessment ownership,
  no-assessment redirect, reassessment isolation, CSRF, POST-redirect-GET,
  append-only/idempotent writes, and private-value-free contention handling;
- exact assessment-context and one-practice-at-a-time provide/N/A/defer form
  mappings with no inferred or preselected factor values;
- explicit current-epoch reviewed-candidate cohorts, unchanged no-context
  legacy recommendations, missing-capacity withholding, and exact
  context-aware ordering;
- distinct cohort-bounded alternatives and no-eligible-alternative behavior
  without practice, evidence, score, completion, or activation mutation;
- Personal OS authored-text isolation from ranking, non-Personal-OS pages,
  messages, logs, existing exports, evidence/score snapshots, reports, and
  activation;
- stale, cross-user, cross-epoch, inactive-protocol, malformed-snapshot, and
  service-failure requests failing closed;
- deterministic read-only `GG-M6C-PILOT-READINESS-1.0` JSON, empty-state
  acceptance, tamper diagnostics, privacy-safe output, and no database writes.

`make e2e` uses Playwright Chromium for the ten established browser journeys
plus the M6C-04 Personal OS/context journey:

1. login, Pilot 002 home, and developmental profile;
2. mobile keyboard content access, five-protocol setup coverage, no horizontal
   overflow, score-boundary copy, and desktop/mobile walkthrough screenshots;
3. non-instrumental-play setup and action-specific compact check-in;
4. emotional-cue setup, anti-mind-reading boundary, and action-specific check-in;
5. boundary setup, anti-coercion and retaliation exclusions, and action-specific check-in;
6. accessible attention-presence setup, condition comparison, and action-specific check-in;
7. all 50 required assessment questions, result save, and 6/15/37 persistence;
8. GGA11 import and supported GGA1 import;
9. recommendation explanation, seven-step setup, start, pause/resume, draft,
   M2 evidence submission/detail, ledger, minimized JSON download, all three
   actions, M3B evidence-updated profile state, final review, completion, and
   mastery disclaimer.
10. mobile/desktop optional pilot feedback, journey-stage progressive
    disclosure, explicit no-telemetry and non-developmental boundaries,
    categorical submission, confirmation, and privacy-minimized download.
11. authenticated Personal OS progressive disclosure; exact private-data
    notice; synthetic identity/audit, season/capacity, provide/N/A/defer
    submissions; partial reviewed-cohort ranking; distinct alternative;
    no-context/reassessment isolation; keyboard focus, error association,
    200-percent zoom, reduced motion, 390-by-844 no-overflow behavior; and
    synthetic desktop/mobile retained screenshots.

The server-side golden test and browser flow complement each other: the first
deep-compares every canonical output, while the second proves that the mounted
UI reaches and persists that engine.

Playwright retains traces and failure screenshots under `test-results`. GitHub
also retains the passing `pilot-walkthrough` desktop/mobile screenshots in the
`playwright-results` artifact for seven days. Review that artifact as described
in `docs/pilot/PILOT_READINESS_CLOSEOUT.md`.

## Docker acceptance

Run:

```bash
make compose-smoke
```

This builds and starts the real production image in an isolated Compose
project. It proves the mapped-port health and CSRF login path, non-root user,
migrations, repeated canonical seeding, evidence and score replay, named-volume
persistence across forced recreation, one-time bootstrap behavior, online
backup integrity, restore, all applicable readiness contracts, and graceful
Gunicorn shutdown. The M6C drill also creates conspicuously synthetic Personal
OS/context revisions through public services, builds a deterministic priority
result, opens the authenticated browser surface over the mapped port, and
verifies revision/result hashes plus friendship-only activation across
recreation and backup/restore.

The command never uses the deployment `.env`. Its temporary credentials,
Compose project, and volume are removed on exit. Set `SMOKE_APP_PORT` only
when a fixed test port is required.

`.github/workflows/verification.yml` runs quality/readiness, the ten
Playwright journeys, and this exact Docker Compose drill on pull requests and
`main`. One aggregate **Pilot readiness gate** succeeds only when all three
jobs succeed. Configure branch protection to require that aggregate check for
pilot-bound merges.

## M6D-01 authoring gate

`make m6d-01-check` builds an isolated migrated and idempotently seeded
database, checks report freshness, replays the fourteen synthetic typed cases,
calls both prerequisite readiness contracts, and verifies the exact cohort and
inactive ledger state without database writes. It is included in the full
repository contract, hosted quality job, and each Compose initial,
recreation, and restore phase. Its tests pin permanent cohort facts while
shared report tests derive any later source-catalog frontier from canonical
state.

## Current scoring boundary

M1 proves guided UX and static assessment persistence. M2A tests event-level
evidence classification and base mass. M2B tests read-only audit, export,
replay, and calibration behavior. M3A tests task-to-lever allocation and the
accepted posterior contract. M3B tests its bounded activation for the
friendship protocol.

Current state, need rank, and active-practice order may now change after
eligible submitted evidence. Tests prove that assessment baselines, raw
self-report, orientations, archetypes, completion, and final review remain
separate. Dynamic context priority and additional score-activated protocols
remain outside M3B.
