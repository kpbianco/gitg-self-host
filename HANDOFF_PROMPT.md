# Codex / Work Tab Handoff Prompt

Use the following prompt in the new GitHub-connected Work/Codex session:

---

You are taking over development of Grounded Growth in `kpbianco/gitg-self-host`.

Start by reading, in order:
1. `AGENTS.md`
2. `docs/PROJECT_HANDOFF.md`
3. `docs/PRODUCT_DECISIONS.md`
4. `docs/program/M6_CURRICULUM_EXPANSION.md`
5. `docs/practice-content.md`
6. `docs/pilot/PILOT_002_FINDINGS.md`
7. `docs/SCORING_DESIGN.md`
8. `MANIFEST.tsv`

Then inspect the canonical data under:
- `data/curriculum/`
- `data/model/`
- `data/assessment/`
- `data/notion/`
- `data/practices/`

Treat `legacy/` as provenance only. Do not build implementation behavior from legacy notes when canonical files disagree.

Work only on the milestone batch explicitly authorized by the repository
owner. M1 through M3B, M4A–M4E, M5A, and M5B are reviewed and merged;
M6A is reviewed and merged; Decisions 023–046 are accepted. Decisions 047–049
describe the proposed M6B contracts and remain proposed until M6B review.
M4A adds score-inactive non-instrumental play; M4B adds score-inactive
emotional cue detection; M4C adds score-inactive boundary practice; M4D adds a
score-inactive attention-presence experiment. M4E adds the read-only
`GG-PILOT-READINESS-1.0` boundary, aggregate GitHub gate, retained browser
walkthrough, and keyboard/mobile hardening. Further protocol or score
activation must proceed in separately authorized, reviewable batches.

Use the binding stack in `AGENTS.md`: a Python/Django monolith with Django
templates, local assets, SQLite, Gunicorn, pytest, Ruff, Playwright, Dockerfile,
and one Docker Compose application service. The earlier Next.js suggestion is
superseded by ADR 0001. Do not add a Node.js runtime server.

The implemented M1 boundary includes:

- canonical curriculum/profile import with stable IDs and version metadata;
- assessment v1.1 taking plus GGA11/GGA1 import;
- concise home/profile and recommendation explanation;
- seven-step setup, active practice, compact draft/submitted check-ins;
- active/paused/stopped/completed states and final review;
- one complete `Deepen One Existing Friendship` protocol;
- inactive placeholders for the four additional protocols in `AGENTS.md`;
- no score mutation.

The M2A boundary adds immutable, replayable `GG-EVIDENCE-1.0` events and
conservative M1 backfill. It stops before task-to-lever allocation, posterior
updates, score snapshots, and dynamic recommendations.

The M2B boundary adds an authenticated evidence ledger, privacy-minimized
deterministic export, strict read-only replay verification, and synthetic
direction-complete calibration fixtures. It changes no evidence mathematics
or profile score.

The M3A boundary adds exact/reconstructed baseline mass, an explicit stable
practice-to-competency link, canonical structured task weights, a pure
direction-aware posterior projection, golden fixtures, and an unsaved profile
preview. It creates no current score, score snapshot, need/rank update, or
dynamic recommendation.

The M3B boundary activates that exact accepted math only for the friendship
protocol. It adds separate 37-lever current state, immutable hashed transition
snapshots, atomic/idempotent event processing, deterministic rebuild and
audited reversal, assessment v1.1 provisional-need recalculation, and active
protocol ordering from canonical weights. Assessment baselines, raw
self-report, orientations, archetypes, completion, and human worth remain
unchanged.

The M4E boundary verifies the exact five-protocol/fifteen-action inventory,
canonical parent and target links, Pilot 002 completeness, evidence replay,
score-state replay, and friendship-only score activation without writing
state. `make pilot-check` exercises the contract from a fresh isolated
database.

M5A adds a bounded private-pilot operator guide plus optional append-only
`GG-PILOT-FEEDBACK-1.0` usability records. Timing uses participant-selected
broad bands, not instrumentation. Its deterministic
`grounded-growth-private-pilot-export-v1` allowlist excludes identity, record
IDs, exact timestamps, free text, private context, assessment data, evidence,
scores, orientations, and archetypes. Feedback never enters assessment,
evidence, ranking, scoring, completion, orientation, or archetype logic. M5A
adds no protocol, remote telemetry, or score activation.

M5B is the findings closeout from the first owner-operated session. It
progressively scopes pilot-feedback questions to the selected journey stage,
scopes check-in observations to the selected action's reviewed evidence
markers, and requires a real attempt before a new evidence submission. It
also adds a preview-first, exact-user operator purge for the optional
pilot-feedback table. Existing feedback, check-ins, evidence, score
transitions, and replay mathematics remain unchanged. Decisions 039–041 are
accepted.

M6A replaces the hard-coded protocol tuple with the manifest-listed canonical
source under `data/practices/`. Five `projected_legacy` packages preserve the
exact five-protocol/fifteen-action runtime fingerprint and friendship-only
score activation. Source, family, risk, scoring-policy, research-gap,
expert-review, activation, coverage, and originality controls are source-only;
M6A adds no migration, protocol, action, UI, evidence math, ranking math, or
score activation. `make curriculum-check` is additive to the unchanged
`make pilot-check`.

The product direction is a guided life OS for people who may be driven but
misdirected or operating on autopilot. Assessment/personality are framing,
not headline or destiny. The eventual flow connects a concise
Truth/Autopilot Audit, mission, principles, anti-goals, season/capacity,
priority stack, weekly execution, and proof-based review while showing only a
small context-fit set of practices.

M6B is the current proposed batch. It adds pure
`GG-TYPED-EVIDENCE-1.0` / `typed-evidence-rules-v1` evaluation,
evidence-only `GG-COMPETENCY-EVIDENCE-SHADOW-1.0`, one-way
`GG-COMPETENCY-LEVER-SHADOW-1.0`, separate
`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0`, and additive
`GG-COMPETENCY-EVIDENCE-READINESS-1.0`. It must not add a migration, UI,
protocol, action, context-priority input, or score activation.

Assessment v1.1 creates lever baselines, not competency baselines. A
lever-derived competency summary never feeds direct competency state.
Typed events may contribute at most once through the complete canonical
parent mapping, remain attached to their assessment epoch, and fail closed on
unknown versions. Existing v1 replay and friendship-only production scoring
remain exact.

`ER-M6A-003` remains pending and `RG-M6A-002` remains open. Implementation and
software readiness may complete, but M6B acceptance and mass authoring remain
blocked until measurement, accessibility, and privacy/safety review is
truthfully recorded. Do not fabricate completed reviewer roles or weaken that
gate.

M6C-01 and M6C-02 are merged with explicit context/defer and private append-only
Personal OS identity/Truth-Autopilot foundations. M6C-03 adds the backend-only
`GG-CONTEXT-PRIORITY-1.0` formula, withholding, deterministic alternatives,
canonical privacy-minimized results, and additive readiness without migration,
persistence, ordinary UI, scoring, or activation. M6C-04 owns browser
collection and presentation. Representative vertical slices begin after M6C
as Phase B.

Acceptance criteria are in `docs/PROJECT_HANDOFF.md`. Add automated tests for
every testable criterion. The app must pass `make compose-smoke` in a
Docker-capable environment.

Before changing code:
1. Audit the repository and data package.
2. Confirm the accepted architecture and make a concise batch plan.
3. Identify data inconsistencies or missing canonical inputs.
4. Do not ask me to restate background already in the repository.

Then implement in reviewable batches. For each batch:
- run Ruff, Django checks, pytest, and applicable Playwright tests;
- run `make pilot-check`;
- run `make curriculum-check`;
- run `make competency-evidence-check` for M6B and later;
- audit against the product doctrine;
- report exact passes/failures;
- open a PR and ask me to approve it.

Do not generalize score activation merely because M4 adds a protocol. A newly
score-active protocol requires its own reviewed canonical mapping, evidence
semantics, and golden coverage.

Do not repurpose M5A product feedback as an applicability, ranking, evidence,
or score input. That would replace the accepted pilot privacy/consent boundary
and requires a separately authorized milestone.

---
