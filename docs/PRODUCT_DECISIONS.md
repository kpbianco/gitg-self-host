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
**Status:** Accepted after M4A review

`PRACTICE-PLAY-01` is an executable evidence-capturing protocol anchored to
canonical competency `26.01`, but `score_active` remains false. Its submitted
check-ins create replayable evidence events and no score snapshots. Score-state
replay selects explicitly score-active protocols only, preserving the reviewed
friendship-only M3 boundary.

## Decision 028 — Reuse the versioned observation vocabulary
**Status:** Accepted after M4A review

M4 protocols configure user-facing labels and action rules over the existing
`GG-EVIDENCE-1.0` observation vocabulary. M4A does not add fields to the v1
snapshot because doing so would change historical replay. A genuinely new
observation vocabulary requires a separately versioned evidence contract.

## Decision 029 — Emotional cues remain hypotheses
**Status:** Accepted after M4B review

`PRACTICE-EMOTIONAL-CUES-01` is anchored to canonical competency `16.03`,
Nonverbal communication. Its intervention separates observable changes from
interpretation, requires more than one plausible explanation, and prefers a
neutral direct question over inference. Eye contact, facial expression,
posture, tone, and distance must not be treated as universal indicators or
used to diagnose intent, emotion, disability, or neurotype.

## Decision 030 — Recommendation targets follow the canonical parent
**Status:** Accepted after M4B review

The placeholder's earlier broad targets `L24` and `L06` are not retained as a
runtime scoring or recommendation mapping. Canonical parent `16.03` maps to
L23, L24, and L05; M4B uses `L24` as its non-empty recommendation-target
subset. It does not invent an L06 link, parse display text, or activate
scoring.

## Decision 031 — Low-stakes boundary practice uses competency 11.10
**Status:** Accepted after M4C review

`PRACTICE-BOUNDARY-01` is anchored to canonical competency `11.10`, Saying no
and ending responsibly. That competency directly supports declining demands
and closing commitments cleanly without requiring the guided intervention to
enter the higher-risk bodily-autonomy or harmful-relationship scopes of
`12.12` or `17.06`. Its structured mapping is L25 `0.40`, L36 `0.25`, L10
`0.20`, and L29 `0.15`; the protocol targets only L25 as a non-empty subset
and remains score-inactive.

The setup is restricted to a low-stakes request, recurring expectation, or
optional commitment where direct communication is reasonably safe. Abuse,
coercive control, stalking, discrimination, unsafe dependency, and likely
retaliation require safety planning and appropriate trusted, professional,
legal, medical, or organizational support rather than this protocol.

## Decision 032 — Boundary completion requires statement and follow-through
**Status:** Accepted after M4C review

A boundary in M4C describes the user's own participation and proportionate
response; it is not a threat, punishment, withdrawal of care, silent test, or
method of forcing agreement. Completion requires both a directly stated
boundary and a proportionate follow-through or restatement within seven days.
The reusable completion configuration therefore supports `marker_mode=all`
while preserving the previous `any` default for reviewed protocols.

Both observations use the unchanged `GG-EVIDENCE-1.0` vocabulary. Boundary
submissions create immutable evidence events but no score snapshot, current
lever-state change, or recommendation-order change.

## Decision 033 — Attention-presence practice uses competency 08.02
**Status:** Accepted after M4D review

`PRACTICE-PRESENCE-01` is anchored to canonical competency `08.02`,
Mindfulness and present attention, because its intervention practices a
bounded period of sustained presence and earlier recognition of distraction.
It is not a broad attention audit across the user's life. The structured
mapping is L08 `0.75`, L03 `0.15`, and L17 `0.10`; the protocol targets only
L08 as a non-empty recommendation subset and remains score-inactive.

M4D does not interpret completion time, output, or distraction count as
mastery. It requires no tracking application, browser history, camera,
microphone, or observation of another person.

## Decision 034 — Presence is an accessible condition comparison
**Status:** Accepted after M4D review

The intervention compares the same low-stakes 15-minute activity under usual
conditions and after changing exactly one user-controlled condition, then
repeats the more workable condition within seven days. The relevant
observation is whether the user noticed and returned attention more readily,
including contradictory evidence that the change did not help.

Stillness, silence, eye contact, and zero distraction are not requirements.
Movement, fidgets, assistive technology, reminders, and alerts needed for
access or safety remain available. The experiment must not run while driving,
operating equipment, supervising a hazard, or after disabling emergency,
accessibility, or caregiving alerts. Completion uses the existing reviewed
all-marker rule and creates immutable evidence without a score snapshot or
lever-state change.

## Decision 035 — Pilot readiness is a versioned read-only contract
**Status:** Accepted after M4E review

`GG-PILOT-READINESS-1.0` freezes the reviewed post-M4 software boundary:
canonical source/database counts, the exact five protocols and fifteen
actions, their reviewed configuration fingerprint, stable parent and
recommendation-target links, Pilot 002 completeness, draft/evidence
separation, friendship-only score activation, evidence replay, and score-state
replay.

The verifier performs no seed, repair, backfill, score processing, or profile
write. It fails closed on drift and is paired with a separate isolated drill
that constructs the expected state through the real migration and startup
commands. A future protocol or scoring expansion must version or deliberately
replace this contract rather than silently weakening it.

## Decision 036 — Pilot release requires aggregate automation and human review
**Status:** Accepted after M4E review

One GitHub **Pilot readiness gate** depends on quality/pytest, Playwright, and
the production Docker Compose drill for the same commit. The Playwright job
retains desktop/mobile walkthrough screenshots and failure diagnostics.
Branch protection is an instance-owner setting and should require this
aggregate check for pilot-bound merges.

Automation proves stable behavior, not visual judgment or participant
experience. A human must review the retained artifact and the live local
deployment before pilot use. This gate does not claim clinical, psychometric,
accessibility-pilot, or longitudinal validation and does not authorize another
protocol or score-active mapping.

## Decision 037 — Pilot feedback is a separate product-data domain
**Status:** Accepted after M5A review

`GG-PILOT-FEEDBACK-1.0` stores optional usability observations in a dedicated
append-only model. A record may reference an active protocol by stable ID only
to identify the product surface. It is not a check-in, developmental evidence,
an applicability factor for ranking, or an input to assessment, score state,
completion, orientations, or archetypes.

The participant may report recommendation fit, a rough setup/check-in time
band, a confusing step, and accessibility or safety friction. Free text is
optional, locally stored, limited to 1,000 characters, and described as
product detail rather than a monitored support channel.

## Decision 038 — Pilot measurement is explicit and privacy-minimized
**Status:** Accepted after M5A review

M5A adds no automatic timer, browser analytics, session recorder, tracking
pixel, external asset, or remote telemetry. Timing is a participant-selected
category. The application does not infer duration from page events.

`grounded-growth-private-pilot-export-v1` is deterministic for unchanged
records and built only from an allowlist. It excludes identity, database IDs,
exact timestamps, every free-text comment, private practice context,
assessment data, developmental evidence, score state, orientations, and
archetypes. The resulting JSON is privacy-minimized but remains sensitive
pilot data rather than anonymous public data.

## Decision 039 — Pilot forms collect one coherent context at a time
**Status:** Proposed for M5B review

The first owner-operated session produced an assessment-stage feedback record
that also identified a practice and answered setup/check-in timing questions.
M5B treats this as a form-coherence defect, not a participant deficit. The
feedback page progressively exposes practice-specific questions only for
relevant journey stages and rejects out-of-scope combinations server-side.

The existing append-only M5A record remains valid historical pilot data and
continues to export unchanged. M5B adds no inferred timing, hidden default,
telemetry, developmental input, or correction of an immutable record.

## Decision 040 — Submitted evidence requires an action-specific attempt
**Status:** Proposed for M5B review

The first session also produced a submitted check-in with no recorded attempt
and observations outside the selected action's reviewed marker set. M5B
requires a real attempted action before submission and derives visible
observation prompts from that action's snapshotted `evidence_rules`. A draft
remains available before the action occurs.

This is a prospective input-integrity gate. It does not change
`GG-EVIDENCE-1.0`, `GG-SCORING-SHADOW-1.0`, `GG-SCORE-STATE-1.0`, historical
event replay, completion criteria, or the friendship-only score-activation
boundary. Existing immutable records are not rewritten or silently
normalized.

## Decision 041 — Pilot-feedback deletion is explicit and user-scoped
**Status:** Proposed for M5B review

Optional pilot feedback is retained locally until the participant agreement
or instance-owner policy says otherwise; there is no automatic retention
timer. Ordinary application use remains append-only. The operator-only
`purge_pilot_feedback` command previews by default and requires an exact local
username plus `--confirm` before deleting only that user's feedback rows.

Deletion does not touch assessment, evidence, score, practice, review,
orientation, or archetype state. Backups may retain deleted rows and remain
subject to the same participant-data agreement.
