# ADR 0016: Calibration reuse is explicit, local, and withdrawable

- Status: Accepted for M6I-04
- Date: 2026-09-02
- Status: Accepted

## Context

Assessment v1.1 already stores item responses and timing as private account
data so results remain reproducible and owner-exportable. M6I-03 proves the
software structure and lists eight empirical evidence gaps, but deliberately
does not turn those ordinary private records into a calibration dataset.

Reusing a completed assessment for research is a second purpose. It requires
an explicit choice, a precise disclosure, withdrawal, data minimization, and a
clear warning that a cross-run pseudonym remains linkable sensitive data.

## Decision

Add `GG-ASSESSMENT-CALIBRATION-CONSENT-1.0`:

1. A participant-created completed assessment is excluded unless its latest
   consent revision is explicitly `consented`. Pilot seed data is ineligible.
2. Consent, withdrawal, and later reconsent are authenticated per-run actions.
   Revisions are append-only, contiguous, idempotent, and snapshot/hash
   verified.
3. One random participant token links explicitly included retakes for the same
   account. The token is pseudonymous, not anonymous.
4. The dataset includes only item responses, answered clarifiers, timing,
   allowlisted response-quality summaries, within-participant run sequence,
   and whole-day intervals.
5. Identity, database and assessment IDs, exact dates, share codes, free text,
   private context, practice/evidence/completion/score history, and derived
   profile outputs are excluded.
6. The user can inspect their exact current contribution. Withdrawal excludes
   that run from future exports without altering the private assessment.
7. The operator command requires an explicit sensitive-data acknowledgement,
   writes a new mode-0600 file, refuses overwrite, and performs no upload.
8. Consent records enter the owner-private archive, account-deletion, backup,
   restore, and rollback boundary. Automated retention does not target them.
9. Collection capability completes zero empirical evidence axes. Sample
   adequacy and every reliability, validity, fairness, fit, burden, and outcome
   claim still require consented data and qualified analysis.

## Consequences

- Ordinary assessment use never becomes research participation by default.
- A self-hosted operator can build a deterministic multi-run dataset without a
  remote service or identity-bearing export.
- Completed runs can support response-distribution and retest analysis later;
  they cannot measure abandonment because abandoned browser-local sessions are
  not collected.
- Withdrawal cannot recall a file already downloaded by an operator, so the UI
  states that limitation before participation.
- Assessment, scoring, recommendations, evidence, completion, and historical
  replay remain unchanged.

## Rejected alternatives

- Default enrollment or a preselected consent box, because ordinary product use
  is not research consent.
- Calling hashed or random identifiers anonymous, because cross-run linkage is
  still pseudonymous participant data.
- Exporting exact timestamps or share codes, because they are unnecessary and
  increase linkage risk.
- Collecting demographics or incomplete sessions in this slice, because both
  require separate necessity, consent, retention, and specialist review.
- Deleting the underlying assessment on withdrawal, because withdrawal governs
  the secondary calibration use rather than the owner's private product record.
