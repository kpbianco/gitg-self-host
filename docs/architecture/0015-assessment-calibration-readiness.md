# ADR 0015: Assessment calibration readiness is source-only

- Status: Accepted for M6I-03
- Date: 2026-09-02
- Decision: 055

## Context

Assessment v1.1 has a deterministic browser scorer, a complete 37-lever item
inventory, adaptive clarifiers, and frozen golden replay. It has not been
psychometrically calibrated or validated with a diverse participant cohort.
Existing software fixtures and one owner-operated pilot cannot truthfully
close that gap.

Before collecting sensitive participant responses, the repository needs an
exact machine-readable statement of what software can prove now and which
evidence remains unavailable. That statement must not require database access
or silently turn committed owner examples into validation data.

## Decision

Add `GG-ASSESSMENT-CALIBRATION-READINESS-1.0` as a deterministic source-only
audit:

1. Hash the frozen v1.1 specification, model, scorer, and coverage artifact.
2. Verify the exact 50 core and 43 clarifier item inventory, global item-ID
   uniqueness, and every lever, family, and orientation reference.
3. Require one direct capability item and one adaptive capability clarifier
   for each of the 37 levers.
4. Recompute each lever's core-signal count, positive weight sum, and effective
   item count and compare them with the frozen 37-row coverage artifact.
5. Keep the existing JavaScript golden replay and GGA1/GGA11 compatibility in
   the readiness gate.
6. Publish eight explicit participant evidence axes with zero completed axes
   and status `data_collection_required`.
7. Read no database or owner/participant-private runtime data and change no
   assessment or production behavior.

## Consequences

- Assessment structure and deterministic scoring drift now fail a dedicated
  CI gate.
- The next empirical milestone begins from an explicit evidence inventory
  instead of an undefined request to “validate the assessment.”
- No response-level calibration dataset is created or exported in this batch.
- Software readiness, Pilot 001 replay, and structural coverage remain
  separate from psychometric, fairness, accessibility-population, and
  participant evidence.
- All assessment, score, recommendation, evidence, and closeout history remain
  byte-for-byte governed by their existing contracts.

## Rejected alternatives

- Treating the Pilot 001 golden fixture as calibration data, because it exists
  to detect software drift and cannot establish population properties.
- Exporting assessment runs by default, because answers, timing, N/A patterns,
  and share codes are sensitive and require a separate consent and governance
  design.
- Calculating reliability or validity from synthetic cases, because synthetic
  scorer coverage is not empirical measurement evidence.
- Changing questions or scoring constants during readiness work, because that
  would create assessment v1.2 and require a separately reviewed migration and
  compatibility decision.
