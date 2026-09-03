# ADR 0017: Private aggregate calibration analysis remains non-validating

- Status: Accepted for M6I-05
- Date: 2026-09-03

## Context

M6I-03 defines eight open participant evidence axes. M6I-04 can produce a
minimized, explicitly consented, pseudonymous local dataset, but collection
software does not show that the available data are sufficient or suitable for
any analysis. Opening that sensitive file in an ad hoc notebook would weaken
the export's fail-closed validation, suppression, reproducibility, and claim
boundaries.

## Decision

Add `GG-ASSESSMENT-CALIBRATION-ANALYSIS-READINESS-1.0`:

1. The operator supplies an exact M6I-04 export to a local, acknowledged
   command. The analyzer verifies the export contract, canonical dataset hash,
   source inventory, consent and disclosure versions, privacy metadata,
   participant pseudonyms, run order, intervals, responses, timing, and
   response-quality allowlists.
2. The analyzer reads no live database, performs no network request or upload,
   and creates a new mode-0600 output without overwriting an existing file.
3. The output has no participant rows, references, raw response or timing
   values, exact timestamps, identity, share codes, free text, private context,
   practice/evidence/completion/score history, or derived profile values.
4. Nonzero aggregate cells below five are suppressed. Exact cohort and source
   totals remain permitted, but the aggregate remains sensitive and is not
   safe for public sharing.
5. Thirty consented participants permits only the status
   `candidate_for_qualified_analysis`. Exploratory consecutive-pair item
   agreement is emitted only for thirty participants with linked retests.
   These are workflow thresholds, not validation thresholds.
6. Missing external reference measures, population-group variables,
   abandoned attempts, fit judgments, and longitudinal outcomes are stated
   explicitly. The analyzer never infers those inputs.
7. Every participant evidence axis remains incomplete and not established;
   `completed_axes` is always zero. Qualified analysis and separate human
   review are required before any evidence claim.
8. A deterministic, conspicuously synthetic in-memory readiness fixture tests
   validation, suppression, thresholds, privacy, and zero claims without
   reading participant data.

## Consequences

- Operators receive one reproducible sufficiency packet instead of handling
  sensitive participant rows in an ungoverned analysis path.
- Data presence and workflow thresholds remain visibly separate from
  reliability, validity, fairness, burden, fit, and outcome conclusions.
- Completed runs may describe completion timing, but cannot establish
  abandonment because abandoned attempts are absent.
- The M6I-04 consent, withdrawal, export, and lifecycle behavior remains
  unchanged.

## Rejected alternatives

- Querying the application database directly, because analysis must consume
  only the reviewed consented export boundary.
- Publishing participant-level or unsuppressed small-cell results, because a
  pseudonym or rare response pattern remains linkable sensitive information.
- Labeling thirty participants as a validated sample size, because adequacy
  depends on a prespecified method, population, estimand, and qualified review.
- Treating retest agreement as reliability, because exploratory agreement is
  not a reliability design or conclusion.
- Inferring fairness groups, fit, abandonment, or outcomes from fields not
  collected under the M6I-04 consent contract.
