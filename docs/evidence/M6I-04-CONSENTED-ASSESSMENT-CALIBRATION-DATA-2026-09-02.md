# M6I-04 consented assessment calibration data evidence

Date: 2026-09-02
Baseline: `306a608990807e34b809b7e86ea94948bd636b42`
Branch: `codex/m6i-04-consented-calibration-data`

## Implemented boundary

- ADR 0016 and `GG-ASSESSMENT-CALIBRATION-CONSENT-1.0` make secondary
  calibration reuse an explicit authenticated choice for one completed
  participant-created assessment. Ordinary assessment use enrolls nothing and
  the Pilot 002 demonstration seed is ineligible.
- Consent, withdrawal, and later reconsent append contiguous hash-verified
  revisions. An unchanged choice is idempotent and withdrawal controls future
  exports without mutating the private assessment.
- One random participant token links a person's explicitly included retakes.
  The export is labeled sensitive pseudonymous data, not anonymous data.
- The deterministic allowlist contains item and clarifier responses, available
  timing, allowlisted response-quality summaries, assessment version/source,
  within-participant sequence, and whole-day retest intervals. Identity,
  database and assessment IDs, exact timestamps, share codes, free text,
  Personal OS/context, developmental history, and derived outputs are excluded.
- The owner may inspect their current contribution. The operator command
  requires `--confirm-sensitive-export`, creates a new mode-0600 file, refuses
  overwrite, and performs no network upload.
- Consent is included in owner-private archive, account deletion, SQLite
  backup/restore, readiness, and migration rollback boundaries. Assessment,
  scoring, recommendation, evidence, completion, and historical replay
  behavior remain unchanged.

## Local verification

- Focused consent, data-lifecycle, backup, deployment-contract, and assessment
  regression suite: 41 passed in 145.98 seconds.
- M6I-03 source-only calibration readiness and JavaScript golden replay:
  passed; 37 lever rows verified, zero participant axes completed, eight open.
- M6I-04 fresh-database migration, bootstrap, canonical seed, empty-consent
  readiness, JSON privacy check, and migration consistency drill: passed.
- Contract, protected-path, manifest, Ruff, Django system, and migration-drift
  checks: passed. The local non-browser run reached 423 passing tests before a
  latent programmatic string-path backup regression failed; the correction's
  exact xdist regression passed. A subsequent full local rerun was externally
  aborted, so the hosted serial result below is the definitive complete-suite
  closeout.

## Hosted verification

- Draft PR: [#50](https://github.com/tranquilWorks/gitg-self-host/pull/50),
  initial feature head `b3d01b7c1524afa8eb426e63ebe20aba289ee393`.
- Verification run [#112](https://github.com/tranquilWorks/gitg-self-host/actions/runs/33687786442):
  Ruff, Django, and pytest passed, including 424 tests with 13 browser tests
  deselected in 2,429.27 seconds and every readiness check, including both
  assessment-calibration gates.
- Docker Compose migration 0013, bootstrap, backup/restore, container
  recreation, and readiness drill: passed.
- The first Playwright attempt had one horizontal-overflow failure in an
  unchanged Personal OS journey. Its isolated same-commit rerun passed all 13
  browser journeys with 424 non-browser tests deselected in 169.21 seconds;
  no product or test change was made in response to the transient failure.
- Aggregate Pilot readiness gate: passed after the successful browser rerun.

## Claim boundary

This evidence supports deterministic explicit-consent local collection
software only. It supplies no participant observations by itself and completes
zero of the eight calibration evidence axes. Completed-run export cannot
measure abandonment. No representative-sample, psychometric, fairness,
accessibility-population, burden, recommendation-fit, cultural, clinical,
longitudinal, effectiveness, mastery, release, deployment, or specialist-
acceptance claim is made. `ER-M6A-003`, `RG-M6A-002`, M6B specialist review,
and every deferred human gate remain open.
