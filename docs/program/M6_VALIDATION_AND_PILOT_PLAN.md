# M6 validation and pilot plan

## Purpose

M6 validation is layered so content completeness, software correctness,
evidence replay, safety review, and human experience are not collapsed into
one pass/fail claim.

## Foundation gates

M6A requires:

- offline JSON Schema validation for the release manifest, packages, source
  registry, risk taxonomy, scoring policies, protocol families, and activation
  ledger;
- stable-ID, uniqueness, reference, path, parent/domain, and target-lever
  validation before database writes;
- exact projection parity with the reviewed five-protocol fingerprint;
- idempotent seeding with five protocols and fifteen actions;
- deterministic 383-row coverage, domain, lever, risk, and originality
  reports;
- an independent passing `GG-PILOT-READINESS-1.0`;
- additive passing
  `GG-CURRICULUM-EXPANSION-READINESS-1.0`;
- unchanged assessment, evidence, score-state, ranking, and replay fixtures.

`make curriculum-check` constructs disposable state, seeds twice, reconciles
evidence and score state, invokes the old verifier through the new additive
contract, and removes the database. `make pilot-check` remains available and
independent.

## M6B software gates

`GG-COMPETENCY-EVIDENCE-READINESS-1.0` is additive to both existing
readiness contracts. It must verify:

- exact independent replay of `GG-EVIDENCE-1.0` /
  `practice-observation-v1`;
- fail-closed dispatch for `GG-TYPED-EVIDENCE-1.0` and
  `typed-evidence-rules-v1`;
- deterministic materialized rule snapshots whose hashes, stable IDs,
  structured inputs, and minimal provenance reproduce exact outputs;
- Boolean, count/frequency, ordinal, duration, artifact,
  conceptual/scenario, objective, consented-observer, qualified-attestation,
  unknown/not-observed, contradiction, and adverse-outcome fixtures;
- evidence-only `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` with an unknown
  zero-evidence state and no invented competency baseline;
- one-way `GG-COMPETENCY-LEVER-SHADOW-1.0`, duplicate-event rejection,
  canonical full-mapping validation, reversal, and no circular feedback;
- separate `GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` that remains false for all
  new typed paths;
- property/invariant coverage for determinism, bounds, input-order
  independence, idempotent replay, exact reversal, withholding, no double
  counting, no baseline mutation, and assessment-epoch isolation;
- deterministic `typed_evidence_capability_v1.csv`,
  `scoring_policy_execution_v1.csv`, and
  `competency_evidence_readiness_v1.json`, with software readiness and
  specialist acceptance reported separately;
- unchanged five-protocol/fifteen-action projection, 5/383 coverage,
  friendship-only activation, and all v1 score/recommendation outputs;
- no migration, UI, new protocol/action, M6C input, or production write.

Passing this software gate does not mean that M6B is accepted.
`ER-M6A-003` remains pending and `RG-M6A-002` remains open. Measurement,
accessibility, and privacy/safety review must be truthfully recorded before
M6B acceptance or mass authoring.

## Content review layers

| Layer | Required evidence |
|---|---|
| Editorial | Individually authored purpose, fit, actions, reflection, examples, and presentation copy |
| Source | Claim-level source IDs, classification, evidence strength, limitations, access and quotation constraints |
| Mapping | Exact parent competency/domain and canonical lever allocation; recommendation targets are a non-empty subset |
| Originality | Exact, normalized, near-duplicate, reflection, action-shape, duration, and evidence-rule report reviewed |
| Accessibility/context | Low-resource, disability/access, cultural, role, pathway, season, and worldview variants reviewed |
| Safety/privacy | Risk class, foreseeable misuse, exclusions, minimum sensitive data, stop/escalation/referral behavior reviewed |
| Evidence | Typed observations, independence, context, repetition, recency, direction, contradiction, adverse outcomes, and withholding reviewed |
| Scoring | Explicit policy and activation-ledger state; deterministic fixtures before any mutation |
| Experience | Ordinary UI language, burden, setup under five minutes where possible, check-in under two minutes, and completion/mastery distinction |

Moderate and high-risk content needs the specialist role specified by the risk
taxonomy. High-risk content remains qualified-only or non-scored unless a
separate decision establishes a safer boundary.

## Context foundation and representative-batch pilot

M6C establishes the minimum context and Personal OS foundation before broad
authoring: applicability, importance, readiness, urgency,
opportunity/resources, current season and capacity, defer/not-now, mission,
principles, anti-goals, priority stack, a concise Truth/Autopilot Audit, and
useful alternatives after “not now.” Personality remains framing or a
tie-break input, never hidden psychometrics.

M6C-02 software validation covers the exact five identity sections and four
audit prompts, four explicit value states, scalar/list bounds, deterministic
UTF-8 snapshots and hashes, authenticated user/assessment-epoch isolation,
append-only and idempotent revisions, explicit SQLite contention, reversible
schema migration, privacy-safe readiness diagnostics, and unchanged prior
exports/recommendations/scoring/activation. The audit wording still requires
owner review, and software fixtures do not establish accessibility, cultural,
safety, clinical, psychometric, longitudinal, participant, release, or
production validity.

M6C-03 software validation covers exact Decimal normalization, inverse burden,
multiplicative formula and half-up quantization; explicit-zero behavior;
N/A/defer/missing-context precedence; stable ordering and distinct
alternatives; active canonical mapping, epoch ownership, latest revision and
hash validation; compact allowlisted result snapshots; synthetic golden
replay; no mutation; and unchanged no-context profile/browser behavior.
`GG-CONTEXT-PRIORITY-READINESS-1.0` accepts empty optional runtime context and
fails closed with privacy-safe diagnostics when persisted context drifts.
Owner formula/explanation/privacy review and later participant usefulness,
accessibility, cultural, safety, clinical, psychometric, longitudinal,
release, deployment, and production validation remain outside the software
claim.

M6C-04 software validation covers latest-assessment ownership and reassessment
isolation; staged exact Personal OS/context definitions; CSRF,
POST-redirect-GET, append-only/idempotent service use, stale/malformed rollback,
and private-value-free contention; provide/N/A/defer mappings with no ordinal
default or inference; explicitly reviewed current-epoch candidate cohorts;
unchanged no-context legacy behavior; exact context-aware order; distinct
alternatives; and authored-text isolation from ranking, other recommendation
surfaces, logs, URLs, reports, existing exports, evidence/score snapshots, and
activation.

Browser checks cover authentication, labels, semantic headings, error focus,
keyboard access, 200-percent zoom, reduced motion, 390-by-844 layout, no
horizontal overflow, and conspicuously synthetic retained desktop/mobile
artifacts. `GG-M6C-PILOT-READINESS-1.0` aggregates the six prerequisite
readiness contracts and verifies exact definitions, authenticated route
registration, five active protocols, friendship-only activation, optional
state validity, no writes, and privacy-safe output. The isolated Compose drill
adds synthetic public-service revisions, deterministic priority replay,
authenticated HTTP, recreation, backup/restore, and clean shutdown evidence.

These checks do not approve the staged language or a participant pilot. Owner
prompt/factor/explanation/privacy/partial-cohort and retained-artifact review,
required hosted CI on the exact candidate commit, and a separate pilot
decision remain mandatory. M6C-04 does not establish recommendation usefulness,
M6B governance, specialist review, accessibility-population, cultural-safety,
clinical, psychometric, longitudinal, participant, release, deployment,
production, or mastery validation.

After M6C, the Phase B representative vertical slices should exercise protocol
families, risk classes, evidence policies, N/A paths, and accessibility
variants. Review:

- whether a user can act without inventing the intervention;
- whether N/A/defer produces a useful alternative and no deficit language;
- whether actions fit actual burden and resources;
- whether observations are understandable and cannot be spoofed as mere
  completion;
- whether contradictory, adverse, and unknown outcomes remain visible;
- whether privacy and consent language prevents unnecessary sensitive detail;
- whether mobile, keyboard, zoom, reduced-motion, screen-reader, and
  low-bandwidth use remain workable;
- whether summaries communicate provisional evidence without implying worth
  or mastery.

Usability feedback remains in `GG-PILOT-FEEDBACK-1.0` and never becomes
developmental evidence.

## Release evidence

Every PR report includes:

- objective and exclusions;
- protocol/competency changes;
- before/after competency, domain, lever, risk, scoring-policy, and activation
  coverage;
- source and migration behavior;
- source additions and limitations;
- evidence/scoring versions affected;
- safety and privacy decisions;
- exact command results;
- browser, Compose, screenshot, and human visual-review results;
- originality findings and reviewed exceptions;
- failed, skipped, and unverified criteria;
- known limitations and the proposed next batch.

Passing automation does not constitute clinical, psychometric,
accessibility-population, cross-cultural, or longitudinal validation.

## M6D-01 evidence level

M6D-01 can establish static schema/content integrity, deterministic report
freshness, synthetic typed-rule replay, source/runtime isolation, and an
isolated deployment drill when those commands actually run. It cannot
establish semantic originality, accessibility-population fit, privacy/safety
acceptance, intervention effectiveness, recommendation usefulness, specialist
acceptance, participant readiness, release, deployment, production, or
mastery. A trained reviewer and owner must separately disposition the content,
sources, similarity warnings, and exact candidate CI evidence.
