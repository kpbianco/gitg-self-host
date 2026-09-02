# ADR 0014: Explicit applicability and personal coverage

- Status: Accepted for M6I-02
- Date: 2026-09-02
- Decision: 054

## Context

Decision 053 deliberately preserved canonical coverage across all 383
competencies while allowing a separately labeled personal denominator. The
runtime already stores explicit practice context as immutable, hashed,
assessment-epoch revisions, but the recommendation screen did not offer a
direct not-applicable route and the profile exposed only canonical coverage.

Not applicable must not be inferred from missing, deferred, or zero-valued
context. It also must not create credit, penalize the person, rewrite history,
or make a smaller denominator look like canonical completion.

## Decision

Use the existing `PracticeContext` record and its `not_applicable` factor state.
The recommendation page posts a CSRF-protected explicit response to the
existing context service, then renders the existing distinct-alternative flow.
A later explicit context response appends a new revision and can restore the
competency to the personal denominator.

Add `GG-PERSONAL-APPLICABLE-COVERAGE-1.0` as a read-only service projection:

1. Start with the verified competency rows in the current assessment epoch's
   `GG-COMPOSITE-CLOSEOUT-SCORING-1.0` state.
2. Require exactly one active protocol for each state competency.
3. Verify every in-scope context revision's owner, epoch, canonical snapshot,
   content hash, and contiguous revision sequence.
4. Exclude a competency only when its protocol's latest revision is explicitly
   `not_applicable`.
5. Average the existing completion-credit values over the remaining personal
   denominator. Return unavailable for an empty denominator.
6. Hash the deterministic projection inputs and output for replay diagnostics;
   persist no projection row.

The profile displays personal-applicable coverage, included count, explicit
N/A count, and unchanged canonical coverage together. The projection fails
closed independently: invalid context hides the personal view while a valid
canonical composite state remains visible.

## Consequences

- Applicability stays explicit, reversible by append-only revision, private,
  and scoped to one user and assessment epoch.
- Canonical completion coverage, score snapshots, recommendation mathematics,
  and historical replay do not change.
- A completed competency marked N/A is removed from both the numerator and
  denominator of only the personal view; it does not erase its earned credit.
- No migration or new persisted sensitive field is required.
- The personal view is not mastery, validation, or evidence that the excluded
  competency lacks general value.

## Rejected alternatives

- Changing the canonical denominator, because canonical cross-person and
  replay meaning would drift.
- Treating missing, deferred, or zero as N/A, because those states have
  different semantics.
- Awarding credit for N/A, because applicability is not completion.
- Carrying N/A across reassessment, because the response is current context.
- Persisting a second score state, because the view is derivable and should
  not create another mutation path.
