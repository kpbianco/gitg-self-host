# M6I-03 assessment calibration readiness evidence

Date: 2026-09-02
Baseline: `e20daf5058220322918775b37816073e3bc7892e`
Branch: `codex/m6i-03-assessment-calibration-readiness`

## Implemented boundary

- Decision 055, ADR 0015, and
  `GG-ASSESSMENT-CALIBRATION-READINESS-1.0` define a deterministic source-only
  audit of assessment v1.1.
- The audit hashes the frozen spec, model, JavaScript scorer, and coverage
  artifact and recomputes exact item, reference, signal, weight, and effective-
  item-count coverage for all 37 levers.
- The byte-stable report records 50 core items, 43 clarifiers, 37 levers, seven
  families, six orientations, one direct capability item per lever, and one
  capability clarifier per lever.
- Eight participant evidence axes remain `data_collection_required` with zero
  completed. The generator reads no application database or private runtime
  data.
- No assessment source, model, migration, UI, scoring, recommendation,
  completion, evidence, or replay behavior changes.

## Local verification

- Focused assessment/calibration suite: 14 passed.
- Source-only calibration report and existing JavaScript golden replay: passed;
  37 lever rows verified, zero participant axes completed, eight open.
- Practice-content, competency-evidence, catalog-governance, and composite-
  scoring generated reports: current and deterministic.
- Ruff lint and format: passed.
- Django system check and migration drift: passed; no changes detected.
- Agent quick contract and repository-wide non-browser verification: passed;
  409 passed and 13 hosted-browser tests deselected in 1,997.16 seconds.

## Hosted verification

Pending draft PR publication. Required jobs are Ruff/Django/pytest/readiness,
Playwright core journeys, Docker Compose deployment drill, and aggregate Pilot
readiness.

## Claim boundary

This evidence supports deterministic source-only software readiness. It is not
psychometric, clinical, cultural, accessibility-population, fairness,
participant, longitudinal, release, deployment, mastery, or intervention-
effectiveness validation. `ER-M6A-003` remains pending, `RG-M6A-002` remains
open, and M6B specialist acceptance remains false.
