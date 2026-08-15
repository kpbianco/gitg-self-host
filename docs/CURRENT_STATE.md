# Current state

Last audited: 2026-08-15
Implementation base: `main@a1bc792`

## Completed implementation

- M1A/B through M5A/B are merged.
- M6A canonical practice-content foundation is merged.
- M6B typed evidence, evidence-only competency shadow, one-way lever shadow,
  production eligibility, deterministic reports, and additive readiness are
  merged as software.
- The projected runtime remains five packages and fifteen actions, with
  friendship as the only production score-active protocol.
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
- M6C-04 and its mobile/manifest corrections are reviewed and merged. The
  authenticated Personal OS/context journey and additive browser/deployment
  readiness preserve the unchanged scoring and recommendation contracts.

## Current implementation

- M6D-01 authors exactly four representative low-risk draft packages for
  competencies `08.06`, `09.12`, `10.02`, and `13.02` across four domains and
  four distinct intervention/evidence families.
- The canonical source catalog is nine packages and twenty-nine actions; 374
  competencies remain explicitly uncovered. The four new packages are
  inactive, unprojected, `SP-SHADOW-ONLY`, and production-ineligible.
- A fail-closed source-only typed-rule loader branch, fourteen synthetic action
  fixtures, deterministic reports, and read-only
  `GG-M6D-01-AUTHORING-READINESS-1.0` verify exact identities, hashes,
  governance, and no database writes.
- The five-protocol/fifteen-action runtime, historical replay, M6C behavior,
  recommendation behavior, and friendship-only score activation remain exact.

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

1. Complete M6D-01 exact local/Compose/hosted-CI validation, trained content
   and source review, retained evidence review, and owner PR disposition.
2. Continue representative vertical-slice protocols only through separately
   governed Phase B batches.
3. Stable report-derived domain cohorts of approximately 8–15 competencies per
   human-reviewed target PR.
4. Whole-library scoring dispositions and shadow calibration.
5. Separately approved controlled activation cohorts.
6. Full integration, operations hardening, and diverse multi-cycle validation.

Run the additive source cohort gate with `make m6d-01-check`. Required hosted
CI, trained semantic/originality/accessibility/privacy/safety review, retained
evidence review, and owner approval on the exact candidate commit remain
manual merge gates unless retained evidence records them as actually completed.

## Automation boundary

The target autopilot creates and repairs draft PRs but never merges Grounded
Growth target PRs. Control-plane batch-contract PRs may auto-merge after schema
and CI pass. Generated content, source research, fixtures, and CI do not replace
specialist or participant validation.
