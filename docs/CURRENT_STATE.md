# Current state

Last audited: 2026-08-14
Implementation base: `main@713d1a9`

## Completed implementation

- M1A/B through M5A/B are merged.
- M6A canonical practice-content foundation is merged.
- M6B typed evidence, evidence-only competency shadow, one-way lever shadow,
  production eligibility, deterministic reports, and additive readiness are
  merged as software.
- Current canonical practice coverage remains five packages and fifteen actions
  across 383 competencies; 378 competencies are explicitly uncovered.
- Friendship remains the only production score-active protocol.
- M6C-01 is merged. It adds versioned, assessment-epoch-scoped context/defer
  persistence, deterministic snapshots and hashes, and additive readiness
  without changing recommendations or ordinary UI.
- M6C-02 is reviewed and merged. It adds the exact five
  identity sections and four descriptive Truth/Autopilot Audit responses as
  private, append-only, assessment-epoch-scoped revisions with deterministic
  snapshots and additive readiness. It adds no UI, recommendation, scoring,
  activation, export, deletion, or retention behavior.
- M6C-03 is reviewed and merged at `c7b51c1`. It adds a pure,
  versioned Decimal engine over verified latest context and unchanged
  `GG-NEED-RANKING-1.0` base priorities, deterministic N/A/defer alternatives,
  privacy-minimized canonical results, and additive read-only readiness. It
  adds no migration, persistence, browser integration, scoring write, or
  activation.

## Current implementation

- M6C-04 is implemented on the current review branch. It adds one
  authenticated latest-assessment Personal OS entry point with concise staged
  identity/audit, season/capacity, and per-practice context forms.
- The browser presenter supplies the unchanged M6C-03 engine only explicitly
  reviewed active practices in the current epoch, preserves exact no-context
  legacy recommendation behavior, and shows a deterministic distinct
  cohort-bounded alternative or explicit no-alternative state.
- Authored Personal OS text remains visible only on its owner's authenticated
  Personal OS surface and is excluded from ranking, explanations, other
  recommendation pages, existing exports, evidence/score state, and activation.
- Additive read-only `GG-M6C-PILOT-READINESS-1.0` plus browser and Compose
  wiring verify the six prerequisite contracts, route/authentication boundary,
  five active protocols, friendship-only activation, synthetic state replay,
  recreation, and backup/restore without persisting priority results.
- M6C-04 adds no model, migration, protocol/action, dependency, external
  service, remote telemetry, weekly execution, dedicated Personal OS/context
  export or purge, evidence/scoring write, or activation change.

## Pending governance

M6B is not accepted. `ER-M6A-003` is pending, `RG-M6A-002` remains open, and
Decisions 047–049 remain proposed. The owner-directed control contract defers
that governance closeout while software/content sequencing continues. This
does not authorize production scoring; all new paths remain non-scored and
friendship remains the only score-active protocol.

Run the local gate check:

```bash
./scripts/ensure-agent-env.py
.venv/bin/python scripts/check-m6b-governance-gate.py
```

## Planned sequence

1. Complete M6C-04 exact local/browser/Compose/hosted-CI validation, retained
   synthetic artifact review, owner prompt/factor/explanation/privacy review,
   and human-reviewed target PR disposition.
2. Approximately 10–12 representative vertical-slice protocols after the
   separately governed Phase B authorization.
3. Stable report-derived domain cohorts of approximately 8–15 competencies per
   human-reviewed target PR.
4. Whole-library scoring dispositions and shadow calibration.
5. Separately approved controlled activation cohorts.
6. Full integration, operations hardening, and diverse multi-cycle validation.

Run the independent M6C foundations with `make context-check`,
`make personal-os-check`, and `make context-priority-check`, then the additive
browser/deployment aggregate with `make m6c-pilot-check`. Required hosted CI,
Compose, retained synthetic desktop/mobile artifact review, and owner approval
on the exact M6C-04 candidate commit remain manual merge gates unless the
retained evidence file records them as actually completed.

## Automation boundary

The target autopilot creates and repairs draft PRs but never merges Grounded
Growth target PRs. Control-plane batch-contract PRs may auto-merge after schema
and CI pass. Generated content, source research, fixtures, and CI do not replace
specialist or participant validation.
