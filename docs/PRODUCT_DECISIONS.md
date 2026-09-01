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
**Status:** Accepted after M5B review

The first owner-operated session produced an assessment-stage feedback record
that also identified a practice and answered setup/check-in timing questions.
M5B treats this as a form-coherence defect, not a participant deficit. The
feedback page progressively exposes practice-specific questions only for
relevant journey stages and rejects out-of-scope combinations server-side.

The existing append-only M5A record remains valid historical pilot data and
continues to export unchanged. M5B adds no inferred timing, hidden default,
telemetry, developmental input, or correction of an immutable record.

## Decision 040 — Submitted evidence requires an action-specific attempt
**Status:** Accepted after M5B review

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
**Status:** Accepted after M5B review

Optional pilot feedback is retained locally until the participant agreement
or instance-owner policy says otherwise; there is no automatic retention
timer. Ordinary application use remains append-only. The operator-only
`purge_pilot_feedback` command previews by default and requires an exact local
username plus `--confirm` before deleting only that user's feedback rows.

Deletion does not touch assessment, evidence, score, practice, review,
orientation, or archetype state. Backups may retain deleted rows and remain
subject to the same participant-data agreement.

## Decision 042 — Full curriculum expansion is a governed multi-PR program
**Status:** Accepted by owner for M6 implementation

Grounded Growth will move from the five-protocol vertical slice toward an
individually authored protocol package for every one of the 383 canonical
competencies. This is a pluralist capability and guided-practice program, not
a perfect-person ranking. Dignity, moral worth, universality, clinical
validity, psychometric validity, and mastery must not be inferred from
coverage or completion.

The program proceeds through reviewed batches. M6A establishes governance and
exact migration only; it does not authorize 378 generated stubs, mass
authoring, new UI, typed evidence execution, or another score-active protocol.
Later authoring should normally remain 8–15 packages per PR and must update
sources, risk, coverage, originality, fixtures, and UI evidence together.

## Decision 043 — Canonical packages project onto the frozen runtime
**Status:** Accepted by owner for M6A implementation

`data/practices/release_manifest.yaml` and its explicitly listed,
schema-validated packages and registries become the canonical protocol source.
The Python tuple is removed. The importer validates the full release,
parent/domain identity, source/risk/policy/family/activation references, and
recommendation-target subsets before database writes.

M6A projects only existing ORM fields and must retain the reviewed five
protocols, fifteen actions, all stable IDs and copy, active availability,
friendship-only score activation, and configuration fingerprint
`274f7244630ed56d56a443a6a699399edade6c67fcf964237559e05b72368e35`.

The practice catalog uses its own content hash.
`CurriculumVersion.source_hash` continues to hash only curriculum, model, and
mapping source bytes, so existing assessment versions do not appear to change
because editorial protocol metadata moved.

## Decision 044 — Evidence layers and typed versions fail closed
**Status:** Accepted architectural boundary from M6A; M6B implementation is proposed in Decisions 047–049

Protocol adherence, direct competency evidence, cross-context transfer, and
current lever state are distinct. Recommendation-target levers are a routing
subset, while any scoring allocation continues to use the parent's full
canonical structured mapping.

M6A preserves `GG-EVIDENCE-1.0`, `practice-observation-v1`,
`GG-SCORING-SHADOW-1.0`, `GG-SCORE-STATE-1.0`, and
`GG-NEED-RANKING-1.0`. It does not stretch friendship-oriented Boolean
markers across the curriculum. A new Boolean/count/ordinal/duration/artifact/
conceptual/observer/objective/qualified evidence contract must have a new
version, explicit dispatch, snapshotted replay rules, migration policy,
direction-complete exact fixtures, and fail-closed unknown-version behavior.
Free text never becomes an opaque score input.

## Decision 045 — Activation is ledgered and expansion readiness is additive
**Status:** Accepted by owner for M6A implementation

Protocol availability, editorial status, evidence capture, shadow testing,
and production score mutation are separate decisions.
`data/practices/registries/activation_ledger.yaml` is the only source for the
runtime `score_active` projection. It retains friendship as the sole
score-active protocol; the other four are shadow-only and inactive for score
mutation.

`GG-CURRICULUM-EXPANSION-READINESS-1.0` does not replace or weaken the
independent `GG-PILOT-READINESS-1.0` contract. It invokes that unchanged
verifier, validates packages and deterministic reports, requires the exact
runtime projection, and records the honest M6A baseline: five projected
packages, 378 unauthored competencies, three low-risk and two moderate-risk
packages, one score-active protocol, and zero source-complete release
candidates.

## Decision 046 — Grounded Growth is a guided life OS, not a curriculum browser
**Status:** Accepted by owner for the M6 program

The core user problem is not merely missing knowledge. A person may be highly
driven while misdirected, fragmented, or operating on autopilot. Assessment,
orientation, personality, and archetype results are diagnostic and framing
inputs; they are not the product headline, destiny, stereotype, or measure of
worth.

The product should connect a concise Truth/Autopilot Audit with mission,
principles, anti-goals, current season and capacity, priority stack,
twelve-month direction, weekly execution, and proof-based review. The ordinary
home experience presents only a small, contextually appropriate set of next
practices. It must not expose the 383-item ontology as a checklist, content
encyclopedia, or giant worksheet.

M6B first resolves typed competency evidence and scoring architecture. M6C
then establishes applicability, importance, readiness, urgency,
opportunity/resources, defer/not-now behavior, and the minimum Personal OS
foundation. Representative 10–12 competency vertical slices follow as
Phase B; generated full authoring begins only after those foundations pass their
exact deterministic and hosted-CI gates.

## Decision 047 — Typed evidence is parallel, explicit, and replay-first
**Status:** Not approved by owner; evidence-capture portions retained, production-scoring proposal superseded by Decision 053

M6B introduces pure `GG-TYPED-EVIDENCE-1.0` evaluation with
`typed-evidence-rules-v1` snapshots. It does not modify
`GG-EVIDENCE-1.0`, `practice-observation-v1`, or any historical event.
Dispatch uses the immutable event and rule versions and fails closed on an
unknown version.

The typed contract represents Boolean, count/frequency, ordinal, duration,
artifact, conceptual, scenario, objective, consented-observer, and minimal
qualified-attestation evidence. It distinguishes unknown, not observed,
inconclusive, not applicable, defer, contradiction, and adverse outcome.
Evidence direction and adversity are independent; an adverse outcome may
force withholding or a safety stop without automatically becoming negative
competency evidence. Typed values have no implicit “more is better” meaning.

Every replay snapshot contains the materialized rule, rule version and hash,
stable protocol/action/competency IDs, scoring-policy ID, structured input,
and minimal provenance. Free text, observer identity, sensitive narrative,
and artifact contents are not opaque score inputs.

## Decision 048 — Competency evidence is evidence-only and flows one way
**Status:** Rejected by owner for production scoring; superseded by Decision 053

Assessment v1.1 creates immutable lever baselines; it does not create a
competency baseline. `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` therefore represents
only direct replay-verified evidence. With no eligible evidence, its state is
unknown rather than a neutral numeric estimate. A lever-derived competency
summary may later inform explanation or routing, but cannot seed direct
competency evidence.

`GG-COMPETENCY-LEVER-SHADOW-1.0` applies one designated competency
contribution per immutable event through the complete canonical parent
mapping. It rejects duplicate event keys and never applies protocol
performance and direct competency evidence as two independent contributions
from the same event. Recommendation-target levers remain routing metadata.
Old evidence stays attached to its original assessment epoch and is never
silently transferred after reassessment.

Both projections are deterministic, reversible, non-persisted M6B outputs.
They do not write assessment baselines, current lever state, score snapshots,
need/rank, recommendations, or activation.

## Decision 049 — Shadow capability does not grant production eligibility
**Status:** Not approved by owner; event-level production eligibility superseded by Decision 053

`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` evaluates production eligibility
separately from evidence capture and shadow projection. Eligibility requires a
satisfied executable policy, valid stable mappings, sufficient replayable
evidence, available lever baseline mass, cleared source/risk/specialist
reviews, and an explicitly approved activation-ledger entry.

M6B leaves all new typed paths production-ineligible and preserves friendship
as the only score-active protocol under the existing v1 contracts.
`GG-COMPETENCY-EVIDENCE-READINESS-1.0` may prove the software inventory,
fixtures, replay, reversal, and invariants, but it cannot clear
`ER-M6A-003`. Measurement, accessibility, and privacy/safety review remains
pending and blocks M6B acceptance, runtime projection, production scoring,
participant release, deployment, and validation claims. Decision 051 permits
only inactive, unprojected, source-only draft authoring while those gates remain
open.

## Decision 050 — The first representative cohort is source-only
**Status:** Accepted for M6D-01 implementation; human content/source review deferred under Decision 051

M6D-01 authors exactly competencies `08.06`, `09.12`, `10.02`, and `13.02`
as four materially distinct low-risk draft packages. They use behavioral-start,
prospective-decision-record, skill-feedback-retry, and bounded home-system
audit/redesign interventions. Each is inactive, unprojected,
`SP-SHADOW-ONLY`, and explicitly score-inactive.

Canonical typed action rules require an adjacent exact protocol, action,
competency, and policy identity and must pass the unchanged
`typed-evidence-rules-v1` materializer. The identity wrapper does not modify
`GG-TYPED-EVIDENCE-1.0`, historical evidence, or an ORM model. The source
catalog may expand to nine packages and twenty-nine actions, while the runtime
remains exactly five protocols, fifteen actions, and friendship-only score
activation.

Synthetic replay demonstrates deterministic software behavior only. The four
drafts remain blocked from source-complete, release-candidate, M6B-accepted,
specialist, participant, intervention-effectiveness, recommendation-usefulness,
mastery, deployment, production, and score-eligibility claims.

## Decision 051 — PFSPAM defers human review until draft coverage is complete
**Status:** Accepted by owner on 2026-08-21

PFSPAM may author fixed M6D and generated M6E competency cohorts, commit and
push the change, open or update the focused target PR, perform the bounded CI
repair loop, mark the exact head ready, and merge it when every required check
passes and no unresolved review thread remains.

This standing authorization applies only to individually authored packages or
explicit non-protocol dispositions that remain inactive, unprojected,
source-only, production-ineligible, and score-inactive. Every cohort must retain
claim-level sources and limitations, risk and policy assignments, deterministic
coverage/originality/replay reports, synthetic fixtures, frozen legacy replay,
the five-protocol runtime, and friendship-only score activation. Exact
duplicates, schema or mapping defects, failed CI, scope violations, forbidden
claims, runtime changes, persistence changes, or activation drift still stop
the batch.

Semantic, source, originality, accessibility, privacy, safety, retained-
evidence, and owner review of intermediate cohorts is deliberately recorded as
deferred rather than passed. After all 383 competencies have an individually
authored draft package or explicit non-protocol disposition, M6B-GOV performs
the consolidated human review and resolves, revises, or rejects the library.

This authorization does not cover runtime projection, production score
activation, participant exposure, release, deployment, production writes,
repository-settings mutation, or specialist, clinical, psychometric,
accessibility-population, cultural, longitudinal, effectiveness, mastery, or
validation claims. Those remain separate human gates.

## Decision 052 — Activate the complete canonical protocol catalog
**Status:** Owner-directed runtime activation on 2026-08-26; event-level score trigger superseded prospectively by Decision 053; consolidated content audit pending

The owner explicitly supersedes the five-runtime/friendship-only boundary for
this batch and directs all 383 canonical protocols to become runtime available
and score active. `SP-STRUCTURED-EVIDENCE-ELIGIBLE` is the common activation
policy. Legacy actions retain `practice-observation-v1`; typed actions retain
`GG-TYPED-EVIDENCE-1.0` and action-specific measurement and provenance rules.

An active protocol is eligible to update the separate current lever state; an
individual check-in is not guaranteed to do so. Unattempted, unknown,
inconclusive, stale, adverse, unobserved, invalid, unconsented, and cross-epoch
evidence is withheld without penalty. Each eligible event contributes once
through its complete canonical parent-competency mapping. Recommendation target
subsets never replace that allocation. Immutable assessment baselines,
replayable evidence, hashed score snapshots, reversal, rebuild, and
completion-not-mastery remain binding.

This software activation does not mark the deferred semantic, source,
originality, accessibility, privacy, safety, specialist, cultural,
psychometric, clinical, participant, longitudinal, or intervention-
effectiveness audits complete. It never authorizes scoring identity, dignity,
qualification, clinical status, or human worth.

## Decision 053 — Composite assessment priority and human-closeout completion credit
**Status:** Accepted by owner on 2026-09-01 for M6I-01 implementation

The owner rejects Decisions 047–049 as the production scoring architecture.
Typed check-ins remain immutable, structured proof, but a new check-in does not
change the additive score state. Production completion credit changes only
when the user explicitly closes a practice after satisfying its configured
minimum and substantive criterion. Assessment v1.1 data, historical
`GG-SCORE-STATE-1.0` rows, evidence events, and score snapshots remain frozen
and replayable.

Assessment remains a concise starting-priority input rather than an earned
competency credit. It supplies 37 lever estimates and seven family rollups.
The 27 domains and 383 competency starting estimates are deterministic
projections from those results and the canonical ontology; they are labeled
assessment-derived rather than directly measured.

For competency `c` with `k` mapped levers, canonical normalized relationship
weight `r(c,l)`, and blended relationship weight `w(c,l)`:

`w(c,l) = 0.50 * r(c,l) + 0.50 * (1 / k)`

Every positive canonical relationship remains represented, stronger mappings
remain stronger, and the weights for each competency sum to one. Family
projection uses the mapped levers' family membership. A preliminary
lever-mapped competency estimate is calculated before its domain rollup, so
the following final assessment composite is acyclic:

`estimate(c) = 0.50 * mapped_lever(c) + 0.25 * mapped_family(c) + 0.25 * parent_domain(c)`

The same weights produce a confidence value. Existing assessment v1.1 gap and
confidence mathematics initialize need; they do not award completion credit.
This structure deliberately lets the concise assessment bias weak areas
without pretending the user answered hundreds of competency questions.

Actions are equal credit units for this version. Check-ins and repetitions may
stage proof for an action, and the user explicitly marks whether the action was
completed. No action or check-in changes global coverage before final closeout.
At the configured minimum, closeout credit is `0.75`; when every defined
action is completed, it is `1.00`. For future protocols with intermediate
counts, credit is linearly interpolated between those endpoints. A repeated
practice uses the maximum active closeout credit for its competency, never a
sum, so repetition cannot farm credit and a later stronger closeout applies
only the positive difference.

Lever and family coverage are normalized by `w(c,l)` relationship mass.
Domain coverage treats its member competencies equally. Canonical coverage is
`1.00` only when every contributing competency has `1.00` credit. Personally
not-applicable coverage may use an explicitly separate denominator, but it may
not be labeled full canonical coverage.

For assessment starting need `A` and earned coverage `G`, remaining need is:

`R = A * (1 - G) ^ 0.5`

Candidate priority combines 50 percent mapped-lever, 25 percent mapped-family,
and 25 percent parent-domain remaining need, applies the candidate
competency's own remaining-credit factor, and then enters the unchanged
explicit M6C context layer. Full-credit competencies therefore leave the next
action queue; partial-credit competencies may return later when still
relevant. Completion is called completion credit, not mastery.

Decision 052 continues to authorize all 383 protocols as runtime available.
This decision supersedes only its prospective event-level score trigger.
`ER-M6A-003` remains pending, `RG-M6A-002` remains open, and M6B specialist
acceptance remains false. Owner approval authorizes deterministic software
implementation; it is not psychometric, clinical, cultural, accessibility,
privacy/safety-specialist, participant, longitudinal, or intervention-
effectiveness validation.
