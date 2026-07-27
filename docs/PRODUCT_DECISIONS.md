# Product Decisions

## Decision 001 — Self-hosted consumer app
**Status:** Accepted

Notion remains the content studio. A dedicated web application is the consumer runtime.

## Decision 002 — Protocols, not competencies
**Status:** Accepted

The app recommends executable Practice Protocols. Competencies remain the curriculum ontology and recommendation target.

## Decision 003 — Static scores for Milestone 1
**Status:** Accepted

M1 may show a score-impact preview but must not mutate mastery or confidence.

## Decision 004 — Evidence before algorithm
**Status:** Accepted

Do not integrate the posterior update algorithm until structured evidence capture passes user testing.

## Decision 005 — Stable IDs over display text
**Status:** Accepted

All joins and imports must use canonical IDs. Display labels are editable and not authoritative.

## Decision 006 — Orientation is not mastery
**Status:** Accepted

Orientation/archetype data influences language, framing, and tie-breaking only.

## Decision 007 — No universal worth score
**Status:** Accepted

No aggregate score may be presented as human value, virtue, or a complete measure of flourishing.

## Decision 008 — Django monolith
**Status:** Accepted

M1 uses a single Python/Django application with server-rendered templates,
local assets, Gunicorn, and one Docker Compose service. The earlier suggested
Next.js architecture is superseded. A separate frontend, API service, and
Node.js runtime would add deployment and state boundaries without helping the
single-user local-instance validation.

## Decision 009 — SQLite for the local single instance
**Status:** Accepted

M1 stores application state at `/data/grounded_growth.sqlite3`, uses Django
migrations, a busy timeout, and WAL where supported. The data directory is a
persistent Docker volume. ORM usage should remain portable, but no PostgreSQL
service is added until deployment needs demonstrate that concurrency or
operational complexity is justified.

## Decision 010 — Browser scoring remains the M1 reference
**Status:** Accepted

Assessment v1.1's canonical JavaScript scoring engine remains the reference
implementation. Golden tests lock its known input/output behavior. Django
serves that exact engine to the authenticated assessment page and validates
the complete persisted result, but does not rewrite its mathematics or enable
its dormant evidence-update functions.

## Decision 011 — M1A before guided workflow
**Status:** Accepted

M1A establishes deployment, authentication, schema, canonical import, and the
Pilot 002 profile. Assessment-taking/import and the practice workflow are M1B
and begin only after M1A review.

## Decision 012 — Submitted evidence is distinct from working state
**Status:** Accepted

Practice check-ins may be saved as drafts. Only explicitly submitted,
timestamped, immutable check-ins appear in evidence history or count toward
completion. Submitted evidence is not converted into a score in M1.

## Decision 013 — Bounded completion without mastery
**Status:** Accepted

The first practice completes only after all three actions have been attempted,
at least two completed, a substantive interaction recorded, and a final review
submitted. Completion records protocol participation only. Every review and
completion screen states that completion does not establish mastery.

## Decision 014 — One current practice
**Status:** Accepted

A user may have one active or paused practice at a time. Pausing is reversible;
stopping is terminal. This keeps the home page and next action unambiguous
while M1 validates the guided experience.

## Decision 015 — Versioned evidence events before score updates
**Status:** Accepted

Each submitted check-in creates one immutable `GG-EVIDENCE-1.0` event in the
same transaction. The event records protocol adherence, structured quality,
independence, bounded context breadth, action-specific repetition,
contradiction, and base evidence mass. It snapshots exact structured inputs
and action rules for deterministic replay without copying private note text.
Drafts create no event.

## Decision 016 — M2 event mass is not lever state
**Status:** Accepted

M2A stops at `e = q × i × b × r`. It does not calculate task-to-lever
coefficients, success/failure contributions, posterior mastery, confidence,
need, task priority, or dynamic recommendations. Existing M1 submissions are
backfilled conservatively: missing context/support stay explicitly unknown,
and absence of contradiction text is not converted into supportive evidence.

## Decision 017 — Evidence auditability before dynamic scoring
**Status:** Accepted

M2B adds a user-scoped evidence ledger, strict read-only replay verification,
and versioned synthetic calibration fixtures before any M3 score update is
designed. Audit surfaces read the immutable `GG-EVIDENCE-1.0` events and never
write assessment, baseline, recommendation, archetype, or orientation state.

## Decision 018 — Privacy-minimized export by allowlist
**Status:** Accepted

The M2B JSON export includes only stable protocol/action IDs, replayable
structured inputs, and event outputs. It excludes user identity, database
record IDs, exact timestamps, person/context labels, all free text,
assessment answers, and share codes. Event sequence is retained so repetition
can be calibrated. The export is deterministic for unchanged records and is
still treated as sensitive behavioral data rather than advertised as
anonymous public data.

## Decision 019 — Explicit practice-to-competency scoring links
**Status:** Accepted after M3A review

A scoreable practice must reference a stable canonical parent competency.
Task-to-lever allocation comes from that competency's structured
`CompetencyLeverLink` rows and must sum to approximately 1.0. The first
friendship protocol references `17.03`, Maintaining friendship. Runtime code
must fail if its recommendation targets are not a non-empty subset of that
mapping and must never parse display text to recover weights. Recommendation
targets remain a separate product-selection concept and are not broadened by
M3A.

## Decision 020 — Direction-aware shadow policy
**Status:** Accepted after M3A review

`GG-SCORING-SHADOW-1.0` multiplies protocol performance by `1.0` for
supportive, `0.5` for mixed, and `0.0` for contradictory evidence before
splitting allocated mass into success and failure. Inconclusive and legacy
direction-unknown events are withheld from posterior and confidence rather
than silently becoming supportive. The policy is visible, versioned, and
golden-tested before activation.

## Decision 021 — Exact baseline mass and read-only M3A
**Status:** Accepted after M3A review

New assessment runs retain the canonical scorer's exact alpha and beta mass.
Pilot 002 mass is reconstructed from rounded published raw/calibrated values
only where the solution is identifiable; ambiguous neutral values remain
unavailable. M3A may render the result as a preview but writes no current score,
score snapshot, need, priority, or recommendation. M3B activation requires a
separate review.

## Decision 022 — Confidence is anchored and monotonic
**Status:** Accepted after M3A review

Assessment confidence already incorporates coverage, response quality, and
consistency. The dormant task helper's mass-only confidence recalculation can
make confidence fall after adding evidence, so M3A does not use it. The shadow
contract starts at stored assessment confidence and adds a bounded gain
`(1 - C0) × E / (E + 1.5)`. Included evidence cannot lower confidence;
withheld evidence leaves it unchanged.

## Decision 023 — Baseline and current state remain separate
**Status:** Accepted after M3B review

`LeverBaseline` remains the immutable assessment record. M3B stores current
alpha/beta mass, provisional estimate, confidence, evidence mass, and need
rank in a separate per-assessment `LeverState`. A newer assessment starts a new
state; evidence tied to an older sprint is never transferred silently.

## Decision 024 — Append-only transitions around atomic score application
**Status:** Accepted after M3B review

Check-in submission, evidence creation, score replay, current-state update, and
the process snapshot commit in one transaction. Every initialization,
processed event, reversal, and actual repair records a full hashed 37-lever
before/after snapshot. An event is processed and reversed at most once.
Reversal retains the evidence event and requires an audit reason. Startup
rebuild is deterministic and idempotent.

## Decision 025 — Dynamic ranking uses the existing provisional need
**Status:** Accepted after M3B review

M3B recalculates assessment v1.1's existing provisional need
`(1 - M)^1.5 × (0.60 + 0.40 × C)` from current estimate and confidence, then
ranks active practices by canonical parent-competency weights. The fuller
context model remains deferred because applicability, importance, readiness,
urgency, and opportunity are not collected as separate per-user inputs.
M3B does not invent hidden defaults or apply an orientation modifier.

## Decision 026 — Unavailable evidence mass fails closed
**Status:** Accepted after M3B review

A baseline without an assessed estimate or exact/identifiable alpha/beta mass
is marked `baseline_only`. It remains visible and may retain its provisional
need, but a practice cannot apply evidence to it. Reassessment is the supported
upgrade path. Pilot 002's four ambiguous neutral levers remain baseline-only;
the four levers used by the friendship practice are identifiable and active.

## Decision 027 — Protocol availability does not imply score activation
**Status:** Proposed for M4A review

`PRACTICE-PLAY-01` is an executable evidence-capturing protocol anchored to
canonical competency `26.01`, but `score_active` remains false. Its submitted
check-ins create replayable evidence events and no score snapshots. Score-state
replay selects explicitly score-active protocols only, preserving the reviewed
friendship-only M3 boundary.

## Decision 028 — Reuse the versioned observation vocabulary
**Status:** Proposed for M4A review

M4 protocols configure user-facing labels and action rules over the existing
`GG-EVIDENCE-1.0` observation vocabulary. M4A does not add fields to the v1
snapshot because doing so would change historical replay. A genuinely new
observation vocabulary requires a separately versioned evidence contract.
