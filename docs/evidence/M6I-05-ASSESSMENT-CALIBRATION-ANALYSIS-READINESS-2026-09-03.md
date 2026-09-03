# M6I-05 assessment calibration analysis readiness evidence

Date: 2026-09-03
Baseline: `d2b326e1760f1904487369623bf51dc37b89c426`
Branch: `codex/m6i-05-calibration-analysis-readiness`

## Implemented boundary

- ADR 0017 and `GG-ASSESSMENT-CALIBRATION-ANALYSIS-READINESS-1.0` define a deterministic,
  local-only analyzer for the exact M6I-04 consented export.
- The analyzer verifies the export schema, canonical dataset hash, source and
  item inventories, consent/disclosure versions, privacy and field allowlists,
  participant and run structure, intervals, responses, timing, and
  response-quality summaries. Unknown, missing, extra, duplicate-key,
  malformed, mis-sequenced, and hash-drifted input fails closed.
- Output is limited to exact cohort/source totals, small-cell-suppressed item
  distributions and timing summaries, allowlisted response-quality summaries,
  workflow-threshold status, exploratory consecutive-pair agreement, and
  explicit per-axis limitations.
- Participant references and rows, raw responses and timing, exact timestamps,
  identity, share codes, free text, Personal OS/context,
  practice/evidence/completion/score history, and derived profile values are
  absent. The aggregate remains sensitive and is not safe for public sharing.
- The operator command requires explicit sensitive-input acknowledgement,
  reads no database, performs no upload, creates mode `0600`, requires distinct
  input and output paths, and refuses overwrite.
- Thirty descriptive participants and thirty participants with linked retests
  are software workflow thresholds only. Every evidence axis remains
  incomplete and not established with `completed_axes` fixed at zero.

## Local verification

- Ruff on the analyzer, commands, and focused tests: passed.
- Focused analysis, M6I-04 consent compatibility, and deployment-contract
  suite: 31 passed in 72.98 seconds.
- M6I-05 synthetic database-free analysis readiness: passed with 30
  participants, 60 completed runs, zero raw values, and zero completed axes.
- M6I-04 fresh-database consent/export readiness: passed with zero active
  participants and zero completed axes.
- M6I-03 source-only readiness and JavaScript golden replay: passed with eight
  axes open and zero completed.
- Practice-content, competency-evidence, catalog-governance, and composite-
  scoring reports: current and deterministic.
- Contract verification passed: manifest, Ruff format/lint, Django system
  check, and migration-drift check are green.
- Exact final-tree repository-wide non-browser verification: 436 passed and 13
  browser tests deselected in 2,087.19 seconds.
- Final manifest and diff checks: passed before publication.
- Hosted results: passed as recorded below.

## Hosted verification

- Draft PR: [#51](https://github.com/tranquilWorks/gitg-self-host/pull/51),
  initial feature head `29958a41dd3dd2d7c6df02b62c87bed3fcee5819`.
- Verification run [#115](https://github.com/tranquilWorks/gitg-self-host/actions/runs/33787894970):
  Ruff, Django, and pytest passed, including 436 tests with 13 browser tests
  deselected in 3,079.57 seconds and every readiness check, including the
  M6I-05 assessment-calibration analysis gate with 30 synthetic participants
  and zero completed evidence axes.
- Playwright passed all 13 core browser journeys with 436 non-browser tests
  deselected in 161.76 seconds.
- Docker Compose migration/bootstrap, authenticated HTTP, backup integrity,
  container recreation, volume persistence, restore, and all readiness drills
  passed, including M6I-05 before recreation and after restore.
- Aggregate Pilot readiness gate: passed.

## Claim boundary

This evidence supports deterministic private aggregate analysis readiness
only. Workflow thresholds and exploratory agreement do not establish sample
adequacy, calibration, reliability, validity, fairness,
accessibility-population validity, burden or abandonment, recommendation fit,
longitudinal association, clinical validity, intervention effectiveness,
release readiness, deployment readiness, mastery, or human worth.
`ER-M6A-003`, `RG-M6A-002`, M6B specialist acceptance, qualified analysis,
and every deferred human gate remain open.
