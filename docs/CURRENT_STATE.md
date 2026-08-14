# Current state

Last audited: 2026-08-14
Implementation base: `main@1a20160`

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
- M6C-03 is implemented on the current review branch. It adds a pure,
  versioned Decimal engine over verified latest context and unchanged
  `GG-NEED-RANKING-1.0` base priorities, deterministic N/A/defer alternatives,
  privacy-minimized canonical results, and additive read-only readiness. It
  adds no migration, persistence, browser integration, scoring write, or
  activation.

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

1. Review M6C-03 formula/dispositions/privacy and complete the later M6C
   browser batch.
2. Approximately 10–12 representative vertical-slice protocols.
3. Stable report-derived domain cohorts of approximately 8–15 competencies per
   human-reviewed target PR.
4. Whole-library scoring dispositions and shadow calibration.
5. Separately approved controlled activation cohorts.
6. Full integration, operations hardening, and diverse multi-cycle validation.

Run the independent M6C foundations with `make context-check`,
`make personal-os-check`, and `make context-priority-check`. Owner formula,
factor-direction, explanation, and fixture/privacy review plus the required
GitHub browser/Compose gates remain before M6C-03 merge.

## Automation boundary

The target autopilot creates and repairs draft PRs but never merges Grounded
Growth target PRs. Control-plane batch-contract PRs may auto-merge after schema
and CI pass. Generated content, source research, fixtures, and CI do not replace
specialist or participant validation.
