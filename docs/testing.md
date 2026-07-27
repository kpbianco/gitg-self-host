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
make e2e
make compose-smoke
```

`make lint` runs Ruff format/lint checks and Django's system check.

`make pilot-check` creates a temporary data directory, applies every
migration, creates the one-time bootstrap user, seeds twice, reconciles
evidence and score state, and then runs the read-only
`GG-PILOT-READINESS-1.0` verifier. It removes its isolated database on exit
and never touches `./var`, `.env`, or the deployed volume.

`make test` covers:

- canonical counts, IDs, mapping coverage, and weights;
- malformed mapping rejection;
- idempotent curriculum, protocol, and Pilot 002 seeding;
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
- append-only `GG-PILOT-FEEDBACK-1.0` persistence and fail-closed export
  validation;
- deterministic `grounded-growth-private-pilot-export-v1` output with
  identity, IDs, timestamps, free text, private context, assessment, evidence,
  score, orientation, and archetype data excluded;
- unchanged assessment, evidence, lever state, snapshots, sprint, check-in,
  review, orientation, archetype, recommendation priorities, and
  recommendation order after feedback submission and export.

`make e2e` uses Playwright Chromium for ten browser journeys:

1. login, Pilot 002 home, and developmental profile;
2. mobile keyboard content access, five-protocol setup coverage, no horizontal
   overflow, score-boundary copy, and desktop/mobile walkthrough screenshots;
3. non-instrumental-play setup and protocol-specific compact check-in;
4. emotional-cue setup, anti-mind-reading boundary, and compact check-in;
5. boundary setup, anti-coercion and retaliation exclusions, and compact check-in;
6. accessible attention-presence setup, condition comparison, and compact check-in;
7. all 50 required assessment questions, result save, and 6/15/37 persistence;
8. GGA11 import and supported GGA1 import;
9. recommendation explanation, seven-step setup, start, pause/resume, draft,
   M2 evidence submission/detail, ledger, minimized JSON download, all three
   actions, M3B evidence-updated profile state, final review, completion, and
   mastery disclaimer.
10. mobile/desktop optional pilot feedback, explicit no-telemetry and
    non-developmental boundaries, categorical submission, confirmation, and
    privacy-minimized download.

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
backup integrity, restore, and graceful Gunicorn shutdown.

The command never uses the deployment `.env`. Its temporary credentials,
Compose project, and volume are removed on exit. Set `SMOKE_APP_PORT` only
when a fixed test port is required.

`.github/workflows/verification.yml` runs quality/readiness, the ten
Playwright journeys, and this exact Docker Compose drill on pull requests and
`main`. One aggregate **Pilot readiness gate** succeeds only when all three
jobs succeed. Configure branch protection to require that aggregate check for
pilot-bound merges.

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
