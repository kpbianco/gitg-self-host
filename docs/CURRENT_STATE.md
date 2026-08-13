# Current state

Last audited: 2026-08-13
Implementation base: `main@4f5987f`

## Completed implementation

- M1A/B through M5A/B are merged.
- M6A canonical practice-content foundation is merged.
- M6B typed evidence, evidence-only competency shadow, one-way lever shadow,
  production eligibility, deterministic reports, and additive readiness are
  merged as software.
- Current canonical practice coverage remains five packages and fifteen actions
  across 383 competencies; 378 competencies are explicitly uncovered.
- Friendship remains the only production score-active protocol.
- M6C-01 is implemented on the current review branch. It adds versioned, assessment-
  epoch-scoped context/defer persistence, deterministic snapshots and hashes,
  and additive readiness without changing recommendations or ordinary UI.

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

1. Complete M6C context factors and concise Personal OS in bounded batches.
2. Approximately 10–12 representative vertical-slice protocols.
3. Stable report-derived domain cohorts of approximately 8–15 competencies per
   human-reviewed target PR.
4. Whole-library scoring dispositions and shadow calibration.
5. Separately approved controlled activation cohorts.
6. Full integration, operations hardening, and diverse multi-cycle validation.

Run the M6C-01 isolated software gate with `make context-check`. Owner factor-
language review and the required GitHub browser/Compose gates remain before
merge.

## Automation boundary

The target autopilot creates and repairs draft PRs but never merges Grounded
Growth target PRs. Control-plane batch-contract PRs may auto-merge after schema
and CI pass. Generated content, source research, fixtures, and CI do not replace
specialist or participant validation.
