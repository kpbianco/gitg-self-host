# Grounded Growth

## Install

```bash
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS,
# APP_BOOTSTRAP_USERNAME, and APP_BOOTSTRAP_PASSWORD.
docker compose up -d --build
```

Open `http://<server-local-ip>:<APP_PORT>`; the default port is
`3000`. Sign in with the bootstrap credentials from `.env`.

Grounded Growth is a self-hosted, evidence-oriented guided-development
application. M1 provides a secure Django runtime, the canonical v1.1
assessment, an immediately usable Pilot 002 demonstration profile, and one
complete guided practice workflow.
M2A adds immutable, versioned evidence readings for submitted check-ins while
leaving every developmental profile value unchanged.
M2B adds a private evidence ledger, deterministic minimized export, strict
replay verification, and calibration fixtures around those same static events.
M3A adds a versioned, direction-aware posterior projection on the profile as a
clearly labeled unsaved preview. The reviewed and accepted M3B contract
activates it for the friendship protocol with separate current state,
immutable transition snapshots, deterministic rebuild/reversal, and dynamic
provisional recommendation ordering.
M4 completes the five-protocol library while keeping friendship as the only
score-active practice. The post-M4 closeout adds a versioned read-only
pilot-readiness audit and one aggregate CI gate over quality, browser, and
production Compose verification.
M5A adds private-pilot operations and optional structured usability feedback
that remains completely separate from developmental evidence and score state.
M5B records the first de-identified pilot findings and narrows both feedback
and check-in forms to coherent journey/action contexts without changing any
evidence or scoring mathematics.
M6A begins the owner-authorized full-curriculum expansion program by moving
the exact five-protocol runtime into manifest-listed canonical packages,
adding source/risk/scoring/activation governance, and generating an honest
383-row coverage baseline. It adds no new protocol, UI, evidence mathematics,
or score activation.
M6B adds a parallel typed-evidence and competency-shadow architecture for
software review. It keeps assessment lever baselines, historical v1 replay,
the five-protocol runtime, and friendship-only production activation
unchanged. Specialist measurement, accessibility, and privacy/safety review
still blocks M6B acceptance. The owner-directed sequence permits later
non-scored software/content work while keeping that governance pending.
M6C-01 adds explicit, versioned context and defer-state persistence plus pure
deterministic snapshot services. It does not yet change recommendations or
ordinary UI.
M6C-02 adds private append-only Personal OS identity and descriptive
Truth/Autopilot Audit revisions without scoring or ordinary UI. M6C-03 adds a
separate deterministic context-priority and alternative backend result while
leaving the existing profile/browser recommendation path unchanged. M6C-04
exposes those reviewed contracts through one concise authenticated browser
journey and an additive deployment/pilot-readiness gate; it adds no model,
migration, score activation, remote telemetry, or release approval.

## Deployment essentials

- Add the server's LAN IP to `DJANGO_ALLOWED_HOSTS`.
- Application data persists in the `grounded_growth_data` named volume.
- The SQLite database is `/data/grounded_growth.sqlite3` inside the container.
- Startup applies migrations, creates the bootstrap user only when no user
  exists, idempotently seeds canonical data, and backfills missing evidence
  events, then deterministically reconciles current score state.
- Health is available without authentication at `/health/`.
- Every other application page requires login; static assets are bundled
  locally.
- Gunicorn listens on `0.0.0.0:8000` inside the container. Compose maps
  `${APP_PORT:-3000}` on the host.

After the first successful login, change the password under **Account** or run:

```bash
docker compose exec app python manage.py changepassword <username>
```

Then remove `APP_BOOTSTRAP_PASSWORD` from `.env`. Restarts never reset an
existing password.

See [deployment](docs/deployment.md) for environment options, updates,
local-network access, shutdown behavior, and the future HTTPS boundary.

## What M1 contains

- Django 6.0 monolith with server-rendered responsive pages.
- Built-in Django authentication, sessions, CSRF protection, and HttpOnly
  session cookies.
- In-application assessment with 50 required questions, optional targeted
  clarifiers, full-question timing, canonical browser scoring, and GGA11 share
  codes.
- GGA11 profile import with supported GGA1 backward decoding.
- Complete M1 schema for assessments, baselines, curriculum links, protocols,
  sprints, actions, check-ins, and reviews.
- Validated import of 27 domains, 383 competencies, 37 levers, and 1,403
  structured competency-to-lever links.
- Idempotent Pilot 002 seed: 37 baselines, six orientations, and the three
  archetypes published in the canonical profile.
- The complete **Deepen One Existing Friendship** protocol data and four
  structured placeholders for later review.
- The complete 14-day **Deepen One Existing Friendship** experience: reason,
  applicability, context, boundaries, start date, defined actions, activation,
  compact draft/submitted check-ins, pause/resume/stop, completion, and review.
- Assessment v1.1 golden and browser coverage for all scoring outputs, GGA11
  generation/import, and supported GGA1 decoding.
- SQLite WAL/busy-timeout configuration and consistent online backup command.
- Ruff, pytest, and Playwright coverage.

## What M2A adds

- Three compact submission choices for support used, context variation, and
  evidence direction.
- Stable action-specific observation rules.
- Pure `GG-EVIDENCE-1.0` classification of protocol performance, structured
  quality, independence, bounded context breadth, repetition, contradiction,
  and base event mass.
- One immutable evidence event per submitted check-in, with exact replay from
  a privacy-minimized input snapshot.
- Conservative, idempotent backfill of existing M1 submissions.
- Plain-language evidence detail with optional collapsed technical audit
  values.
- No lever allocation, baseline mutation, or dynamic recommendation.

## What M2B adds

- One authenticated evidence ledger across practices, newest first and
  filterable by evidence direction.
- A deterministic `grounded-growth-evidence-export-v1` download that excludes
  identity, database IDs, timestamps, private labels, free text, assessment
  answers, and share codes.
- A strict read-only verifier for event coverage, order, stable IDs, and exact
  replay.
- Synthetic golden cases for supportive, inconclusive, mixed,
  contradictory, and legacy-unknown evidence.
- No new evidence algorithm, lever allocation, baseline mutation, or dynamic
  recommendation.

## What M3A adds

- Exact canonical alpha/beta baseline mass for newly taken or imported
  assessments.
- Conservative, labeled reconstruction of Pilot 002 mass only where its
  rounded published values identify one solution.
- An explicit stable link from the friendship protocol to competency `17.03`
  and its structured four-lever weights.
- Pure Decimal `GG-SCORING-SHADOW-1.0` projection with explicit supportive,
  mixed, contradictory, inconclusive, and legacy-unknown behavior.
- Synthetic golden coverage for coefficients, success/failure mass, posterior,
  and confidence.
- A calm authenticated profile preview that states it is not saved and leaves
  recommendations unchanged.
- No current-score model, score snapshot, need/rank write, or dynamic
  recommendation.

## What M3B adds

- A separate 37-lever current state for every immutable assessment baseline.
- Atomic check-in, evidence-event, score-state, and snapshot persistence.
- Full hashed before/after snapshots for initialization, processed evidence,
  reversal, and actual state repair.
- Idempotent event processing, strict replay verification, startup rebuild,
  and audited permanent reversal without deleting the evidence ledger.
- Current estimate and confidence using the exact accepted
  `GG-SCORING-SHADOW-1.0` mathematics.
- `GG-NEED-RANKING-1.0`, which reproduces assessment v1.1's provisional need
  function and orders active protocols from canonical competency weights.
- A baseline-only state and reassessment path when exact/identifiable
  alpha/beta mass is unavailable.
- No assessment-baseline, raw self-report, orientation, archetype, completion,
  dignity, or human-worth mutation.

## What M4 added

- Score-inactive **Schedule Non-Instrumental Play**, with a defined 10-day
  setup, three actions, compact observations, and completion rules.
- Score-inactive **Practice Emotional Cue Detection**, with a defined 10-day
  setup, three actions, direct-clarification requirement, and explicit
  anti-mind-reading and anti-stereotyping boundaries.
- Score-inactive **State and Maintain One Boundary**, with a defined 10-day
  setup, direct statement and follow-through requirements, and explicit
  coercion, punishment, retaliation, and safety exclusions.
- Score-inactive **Complete an Attention-Presence Experiment**, with usual and
  changed 15-minute conditions, an accessible repeat, and explicit
  anti-surveillance and non-productivity boundaries.
- Protocol-configured setup copy, compact check-in fields, completion markers,
  completion-marker modes, and an explicit score-activation flag.
- Stable canonical parents `26.01`, `16.03`, `11.10`, and `08.02` with
  validated recommendation targets.
- All five original protocols became executable. Their historical
  friendship-only score boundary is superseded by M6F.

## Post-M4 pilot readiness

Run the complete source/database boundary from an isolated fresh database:

```bash
make pilot-check
```

For a running instance, use the read-only verifier:

```bash
docker compose exec app python manage.py verify_pilot_readiness
```

It checks exact canonical counts, every protocol/action/link contract, Pilot
002 completeness, evidence replay, score-state replay, and all-383 score
activation. GitHub's **Pilot readiness gate**
additionally requires Playwright and the production Compose drill on the same
commit.

See the
[post-M4 pilot-readiness closeout](docs/pilot/PILOT_READINESS_CLOSEOUT.md)
for the desktop/mobile review matrix and release criteria.

## What M5A adds

- A bounded private-pilot operator/session checklist covering voluntary
  participation, neutral observation, accessibility/safety response, data
  handling, and stop criteria.
- An authenticated optional product-feedback form under **Account**.
- Applicability, participant-estimated setup/check-in time bands,
  confusing-step, and accessibility/safety-friction categories.
- Append-only `GG-PILOT-FEEDBACK-1.0` records in the local SQLite database.
- A deterministic `grounded-growth-private-pilot-export-v1` download that
  excludes identity, record IDs, exact timestamps, free text, private context,
  assessment data, evidence, scores, orientations, and archetypes.
- Tests proving feedback submission and export leave assessment, evidence,
  score state, recommendations, completion, orientations, and archetypes
  unchanged.
- No automatic timer, external analytics, remote telemetry, new protocol, or
  score activation.

See the [pilot feedback contract](docs/pilot-feedback.md) and
[private pilot operations](docs/pilot/PRIVATE_PILOT_OPERATIONS.md).

## What M5B adds

- A de-identified record of the first owner-operated private-pilot session;
  minimized source exports remain uncommitted sensitive data.
- Journey-stage-specific pilot-feedback questions with matching server-side
  validation.
- Action-specific check-in observation prompts derived from reviewed stable
  `evidence_rules`.
- A prospective requirement that submitted evidence records a real attempted
  action; a draft remains available before the action occurs.
- Rejection of observations belonging to another action rather than silent
  normalization.
- A preview-first, exact-user `purge_pilot_feedback` operator command for an
  agreed retention or withdrawal request.
- No migration, telemetry, automatic timing, protocol, evidence/scoring
  algorithm, recommendation input, or score-activation change.

See [Private Pilot 001 findings](docs/pilot/PRIVATE_PILOT_001_FINDINGS.md).

## What M6A adds

- `GG-PRACTICE-CONTENT-1.0` YAML packages under `data/practices/`, validated
  offline against manifest-listed JSON Schemas.
- An exact projection of the five existing protocols and fifteen actions;
  the reviewed runtime fingerprint remains unchanged.
- Canonical source, risk, scoring-policy, protocol-family, research-gap,
  expert-review, and score-activation registries.
- A separate catalog content hash without changing the existing
  curriculum/model/mapping hash or assessment version.
- Deterministic 383-row competency coverage, domain and lever matrices, risk
  register, coverage summary, and anti-boilerplate/originality report.
- The explicit baseline: five projected packages, 378 unauthored
  competencies, five covered domains, thirteen parent-mapped levers, six
  recommendation targets, and zero source-complete release candidates.
- Additive `GG-CURRICULUM-EXPANSION-READINESS-1.0`, which invokes the
  unchanged post-M4 verifier and compares canonical content with the seeded
  runtime.
- No ORM migration, new action, new screen, typed evidence execution,
  scoring/ranking change, or second score-active protocol.

See [canonical practice content](docs/practice-content.md) and the
[M6 program charter](docs/program/M6_CURRICULUM_EXPANSION.md).

## What M6D-01 adds

- Four individually authored low-risk draft packages for competencies
  `08.06`, `09.12`, `10.02`, and `13.02` across distinct behavioral,
  artifact, rehearsal, and audit/redesign families.
- A source catalog frontier of nine packages and twenty-nine actions, with 374
  competencies explicitly unauthored.
- Fail-closed source-only typed rule validation and fourteen conspicuously
  synthetic action fixtures.
- Deterministic cohort reporting and read-only
  `GG-M6D-01-AUTHORING-READINESS-1.0`, runnable with `make m6d-01-check`.
- No runtime protocol/action, model, migration, UI, persistence, ranking,
  scoring, or production-activation change.

## What M6E-FULL-FRONTIER adds

- One deterministic source package for every canonical competency: 383/383
  packages across all 27 domains, with zero uncovered ledger rows.
- 374 generated inactive draft packages with 1,122 stable actions, preserving
  the nine previously authored packages byte-for-byte.
- Complete 37/37 parent-mapped and recommendation-target lever coverage,
  unique generated action IDs/titles/instructions, and deterministic drift
  detection via `make full-frontier-check`.
- Explicit risk and scoring dispositions: high-risk generated packages are
  non-scored; all other generated packages are shadow-only.

## What M6F-ALL-ACTIVE adds

- Runtime projection and score activation for all 383 canonical protocols and
  all 1,151 actions under one exact activation contract.
- Persisted structured typed check-ins for 378 protocols, while preserving the
  five original v1 evidence formats for historical replay.
- Mixed-protocol deterministic scoring through each canonical parent
  competency mapping, including shared-lever aggregation, event withholding,
  immutable snapshots, reversal, and rebuild.
- Exact readiness validation that every runtime protocol, action, target,
  evidence rule, parent mapping weight, and lever total matches canonical data.
- No runtime, model, migration, UI, persistence, recommendation, scoring,
  participant-exposure, release, deployment, or production-activation change.

## What M6B adds

- Pure `GG-TYPED-EVIDENCE-1.0` evaluation from materialized
  `typed-evidence-rules-v1` snapshots, with fail-closed version dispatch.
- Explicit Boolean, count/frequency, ordinal, duration, artifact,
  conceptual/scenario, objective, consented-observer, qualified-attestation,
  unknown/not-observed, contradiction, and adverse-outcome semantics.
- Evidence-only `GG-COMPETENCY-EVIDENCE-SHADOW-1.0`; assessment v1.1 still
  supplies lever baselines and no competency baseline is invented.
- One-way `GG-COMPETENCY-LEVER-SHADOW-1.0`, with duplicate-event rejection
  and no feedback from a lever-derived competency summary.
- Separate `GG-PRODUCTION-SCORE-ELIGIBILITY-1.0`; passing typed or shadow
  checks cannot authorize a production score update.
- Additive `GG-COMPETENCY-EVIDENCE-READINESS-1.0` software verification.
- No migration, typed check-in UI, new protocol/action, M6C context input, or
  score-activation expansion.

M6B software completion is not measurement validation. `ER-M6A-003` remains
pending and `RG-M6A-002` remains open, so M6B acceptance and production use of
the new typed paths remain blocked. The owner-directed sequence separately
permits non-scored M6C and authoring work while retaining those gates.

## What M6C-01 adds

- Append-only `GG-CONTEXT-1.0` assessment-context revisions for season and
  capacity, scoped to one user and immutable assessment epoch.
- Append-only practice-candidate revisions for applicability, importance,
  readiness, urgency, opportunity/resources, burden, and defer/not-now.
- Explicit `unknown`, `not_applicable`, `deferred`, and `provided` states;
  only provided values carry a bounded category or 0–4 ordinal.
- Categorical defer reasons and an optional 1–366 day review horizon that do
  not create a deficit or mutate any assessment, evidence, score, need, rank,
  completion, or worth-related value.
- Deterministic minimal snapshots and SHA-256 hashes, idempotent retries,
  append-only changed revisions, transactional bundle validation, and strict
  reassessment isolation.
- Schema-only reversible migration and additive read-only
  `GG-CONTEXT-READINESS-1.0`.
- No ordinary form or screen, recommendation formula, protocol/action,
  evidence/scoring change, or production activation.

Run the isolated M6C-01 gate:

```bash
make context-check
```

See [context and Personal OS foundation](docs/context-and-personal-os.md).

## What M6C-02 adds

- Append-only `GG-PERSONAL-OS-1.0` revisions scoped to one authenticated user
  and immutable assessment epoch.
- Exactly five identity sections—mission, principles, anti-goals,
  twelve-month direction, and an ordered priority stack—and exactly four
  descriptive Truth/Autopilot Audit responses.
- Explicit `unknown`, `not_applicable`, `deferred`, and `provided` states;
  bounded private authored values; deterministic UTF-8 snapshots and hashes;
  idempotent retries; and explicit retryable SQLite conflicts.
- Read-only `GG-PERSONAL-OS-READINESS-1.0` with privacy-safe diagnostics.
- No ordinary UI, audit or identity score, ranking, alternative
  recommendation, weekly execution, existing export, deletion/retention,
  evidence/scoring, protocol, or activation change.

Run its isolated additive gate:

```bash
make personal-os-check
```

## What M6C-03 adds

- Pure backend `GG-CONTEXT-PRIORITY-1.0` results for an explicit assessment
  epoch and supplied active canonical candidates.
- Exact Decimal multiplication of the unchanged `GG-NEED-RANKING-1.0` base
  priority by explicitly provided applicability, importance, readiness,
  urgency, opportunity/resources, capacity, and inverse burden factors.
- Distinct `not_applicable`, `deferred`, and `missing_context` withholding;
  deterministic primary selection and a distinct eligible alternative after
  N/A or defer.
- Compact canonical UTF-8 JSON and SHA-256 containing stable IDs, versions,
  factor contributions, explanation codes, and context hashes without user
  identity, record IDs, timestamps, Personal OS text, assessment answers, or
  evidence payloads.
- Read-only `GG-CONTEXT-PRIORITY-READINESS-1.0`, including synthetic golden
  replay, canonical mapping and activation checks, and privacy-safe persisted
  context validation.
- No migration, priority persistence, ordinary UI or recommendation-path
  replacement, Personal OS analysis, protocol/content change, score write, or
  activation change. M6C-04 owns browser collection and display.

Run its isolated additive gate:

```bash
make context-priority-check
```

## What M6C-04 adds

- One authenticated Personal OS entry point for the latest user-owned assessment
  epoch, with staged identity, descriptive audit, season, capacity, and
  one-practice-at-a-time context collection.
- Context-aware ordering and distinct alternatives only among explicitly reviewed
  current-epoch candidates, while the legacy recommendation path stays exact when
  context is absent or incomplete.
- Read-only `GG-M6C-PILOT-READINESS-1.0`, which preserves all six prerequisite
  readiness contracts and verifies exact definition IDs, the five baseline
  protocols, friendship-only activation, authenticated routes, and empty or valid
  optional state without printing authored values.
- A Compose deployment drill that uses synthetic values through public services,
  exercises authenticated HTTP, and replays revision/result hashes through
  recreation and verified backup/restore.
- Software and isolated deployment-drill evidence only. M6B governance, owner
  artifact/copy review, participant release, deployment, and production approval
  remain separate.

Run the isolated additive gate:

```bash
make m6c-pilot-check
```

## Product flow

1. Sign in with the bootstrap account.
2. Use the Pilot 002 profile immediately, take assessment v1.1, or import an
   existing GGA11/GGA1 share code.
3. Review the provisional profile and why a practice was selected.
4. Complete the seven-step guided setup; the three actions are already defined.
5. Save check-ins as drafts or submit them with a versioned evidence reading.
6. Review submitted observations in the evidence ledger or download the
   minimized calibration export.
7. Review the versioned evidence-updated working state on the developmental
   profile.
8. Pause/resume when needed, or stop the practice.
9. Submit a final review after the bounded completion criteria are met.
10. During an authorized private pilot, optionally report product friction
    under **Account** without changing any developmental record.

Draft check-ins never appear as submitted evidence. Eligible directional
observations can adjust a provisional current estimate; inconclusive evidence
is withheld. Completing a practice and submitting its final review create no
additional score evidence and do not establish mastery.

## Common commands

Create a local development environment:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Then use:

```bash
make format
make lint
make test
make e2e
make migrate
make seed
make evidence-backfill
make evidence-verify
make score-rebuild
make score-verify
make pilot-check
make practice-reports
make practice-report-check
make curriculum-check
make competency-evidence-check
make context-check
make personal-os-check
make context-priority-check
make m6c-pilot-check
make run
make compose-up
make compose-down
make compose-smoke
make backup
```

The local `migrate`, `seed`, and `run` targets use `./var`; the deployed
container always uses `/data`. `compose-smoke` creates and removes an isolated
Compose project and throwaway volume; it never uses the deployment `.env` or
volume.

## Canonical data

- `data/curriculum/` — 27 domains and 383 competencies.
- `data/model/` — 37 levers, six orientations, 15 archetypes, and weighted
  mappings.
- `data/assessment/` — canonical assessment v1.1 spec, browser engine,
  standalone UI, compatibility code, and fixtures.
- `data/notion/initial_mvp/` — Pilot 002 baselines, static task ranking, and
  starting profile.
- `data/practices/` — manifest-listed canonical protocol packages, schemas,
  registries, research gaps, expert-review queue, and activation ledger.
- `data/evidence/` — manifest-listed M6B typed-evidence engine specification
  and release schemas; it contains no production protocol rules or user data.
- `reports/practice-content/` — deterministic generated coverage, risk,
  originality, typed-capability, scoring-policy, and software-readiness
  controls for the 383-competency expansion.

The importer validates both canonical bundles before writes. Practice
recommendation targets must be non-empty subsets of each parent competency's
structured mapping; runtime score activation comes only from the activation
ledger. It never parses human-readable `Lever Mapping` text. See
[data import](docs/data-import.md).

`legacy/` is provenance and design archaeology only. Canonical structured data
wins when they disagree.

## Backup, restore, and updates

Create an online database snapshot:

```bash
make backup
```

Backups are stored under `/data/backups` in the persistent volume. Follow the
[backup and restore procedure](docs/backup-and-restore.md) before replacing a
database.

For updates:

```bash
make backup
git pull --ff-only
docker compose up -d --build
docker compose exec app python manage.py verify_pilot_readiness
docker compose exec app python manage.py verify_expansion_readiness
docker compose exec app python manage.py verify_competency_evidence_readiness
docker compose exec app python manage.py verify_context_readiness
docker compose exec app python manage.py verify_personal_os_readiness
docker compose exec app python manage.py verify_context_priority_readiness
docker compose exec app python manage.py verify_m6c_pilot_readiness
```

Migrations and canonical seeding run safely on startup.

## Current limitations

- Pilot 002 source files publish only the top three archetypes and do not
  include original answers or a share code; the seed does not invent them.
- Dynamic scoring is activated for all 383 canonical protocols under Decision
  052. A database flag alone cannot activate scoring; canonical activation,
  evidence replay, parent mapping, and score-state validation must all agree.
- Pilot 002 does not publish original alpha/beta mass. Canonical seeding
  reconstructs 33 identifiable rows; L06, L15, L32, and L37 remain
  baseline-only. All four friendship-mapped rows are active.
- Dynamic need remains provisional. M3B updates assessment v1.1's
  gap-and-confidence need function. M6C-04 exposes M6C-03 context priority only
  for an explicitly reviewed current-epoch cohort; absent such context,
  `build_profile_summary` preserves the unchanged no-context path.
- Event reversal is an instance-owner operation and is intentionally
  permanent in M3B. Restore a verified backup if the wrong event is reversed.
- The minimized JSON export omits direct identity and free text, but its
  structured behavioral values can still be sensitive and should be reviewed
  before sharing.
- The separate pilot-feedback export is also privacy-minimized rather than
  anonymous. Optional local comment text is excluded from it, and the
  application does not transmit feedback remotely.
- Private Pilot 001 is one owner-operated session. Its findings support the
  narrow M5B form-coherence changes but do not establish general participant,
  accessibility, psychometric, or longitudinal validation.
- Pilot feedback has no automatic retention timer. The operator may explicitly
  purge one exact user's feedback, but backups may retain prior copies and must
  be handled under the same participant agreement.
- The canonical source catalog now covers all 383 competencies, but none of
  the 374 generated additions is marked source-complete or release-ready.
  Their semantic, source, originality, accessibility, privacy, safety,
  cultural, and specialist dispositions remain pending for consolidated owner
  review even though all 383 are runtime and score active by explicit owner
  direction.
- The five packages retain the friendship-oriented
  `practice-observation-v1` vocabulary for exact replay. The other 378
  protocols persist typed structured evidence; private notes and artifact
  contents do not enter score events.
- `ER-M6A-003` remains a real external governance gate. Passing
  `GG-COMPETENCY-EVIDENCE-READINESS-1.0` does not clear measurement,
  accessibility, or privacy/safety review.
- M6C-01 factor categories and ordinal scales have software-contract coverage,
  not participant accessibility, cultural, longitudinal, specialist,
  psychometric, or clinical validation. Context-specific export, deletion,
  and retention UX remains deferred; database backups contain these private
  local records.
- The canonical JavaScript scorer remains the browser reference. Node.js is
  used by a development golden test only; no Node.js server exists at runtime.
- Direct local-network HTTP is supported. Add Caddy or another proxy later for
  HTTPS or remote access; no proxy is included in M1.
- The product and assessment are not psychometrically validated and do not
  score dignity, virtue, perfection, or human worth.

## Documentation

- [Architecture decisions](docs/architecture/README.md)
- [Deployment](docs/deployment.md)
- [Canonical data import](docs/data-import.md)
- [Assessment integration](docs/assessment-integration.md)
- [Practice workflow](docs/practice-workflow.md)
- [Protocol library](docs/protocol-library.md)
- [Canonical practice content](docs/practice-content.md)
- [M6 curriculum expansion charter](docs/program/M6_CURRICULUM_EXPANSION.md)
- [Context and Personal OS foundation](docs/context-and-personal-os.md)
- [M6 validation and pilot plan](docs/program/M6_VALIDATION_AND_PILOT_PLAN.md)
- [M2 evidence contract](docs/evidence-contract.md)
- [M2B evidence audit and calibration](docs/evidence-audit.md)
- [M3A shadow scoring contract](docs/scoring-shadow.md)
- [M6B one-way competency shadow](docs/architecture/0009-one-way-competency-shadow-and-production-eligibility.md)
- [M3B score-state activation contract](docs/scoring-state.md)
- [Post-M4 pilot-readiness closeout](docs/pilot/PILOT_READINESS_CLOSEOUT.md)
- [Private-pilot feedback contract](docs/pilot-feedback.md)
- [Private pilot operations](docs/pilot/PRIVATE_PILOT_OPERATIONS.md)
- [Private Pilot 001 findings](docs/pilot/PRIVATE_PILOT_001_FINDINGS.md)
- [Backup and restore](docs/backup-and-restore.md)
- [Testing](docs/testing.md)
- [Project handoff](docs/PROJECT_HANDOFF.md)
- [Product decisions](docs/PRODUCT_DECISIONS.md)
