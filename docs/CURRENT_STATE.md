# Current state

Last updated: 2026-09-01
Implementation branch: `codex/m6b-gov-audit`

## M6F all-active implementation

- The canonical catalog contains exactly 383 competency protocols and 1,151
  stable actions across all 27 domains, with zero uncovered competencies.
- All 383 protocols are runtime available and score active under
  `SP-STRUCTURED-EVIDENCE-ELIGIBLE` and `GG-SCORE-STATE-1.0`.
- The five original protocols retain `practice-observation-v1` replay
  compatibility. The other 378 protocols use the typed runtime projection and
  `GG-TYPED-EVIDENCE-1.0` structured observations.
- Typed check-ins persist explicit observation state, provenance, and
  kind-specific structured values. Notes and private artifact contents are not
  score inputs.
- Mixed legacy and typed evidence projects through each protocol's canonical
  parent competency mapping. Shared lever contributions aggregate once per
  event with deterministic replay, snapshots, reversal, and rebuild.
- Unknown, withheld, deferred, not-applicable, inconclusive, adverse, or
  otherwise ineligible evidence remains represented and fails closed or is
  withheld according to the evidence contract.
- Published baselines, raw self-report, orientation results, archetype results,
  stable IDs, completion/mastery separation, and human-worth boundaries remain
  immutable.

## Verification

The readiness chain requires exact agreement between canonical content and the
seeded database: 383 protocols, 1,151 actions, 383 active protocols, and 383
score-active protocols. It validates every protocol's parent, recommendation
targets, actions, evidence rules, canonical mapping weights, and lever totals.

Run the complete local gates with:

```bash
make full-frontier-check PYTHON=.venv/bin/python
make pilot-check PYTHON=.venv/bin/python
make curriculum-check PYTHON=.venv/bin/python
make competency-evidence-check PYTHON=.venv/bin/python
make m6h-weekly-check PYTHON=.venv/bin/python
make m6h-operations-check PYTHON=.venv/bin/python
make catalog-governance-audit-check PYTHON=.venv/bin/python
```

## M6H-01 weekly execution implementation

- The authenticated weekly surface connects verified Personal OS direction,
  existing context priority, one current practice, and one exact action.
- Plans are immutable, append-only, assessment-epoch scoped, and limited to
  the current Monday-to-Sunday window.
- Proof reviews replay only submitted evidence for the exact plan action after
  plan creation and no later than the frozen review cutoff.
- Planning and review create no evidence event, score snapshot, recommendation
  factor, sprint transition, final practice review, or mastery state.
- Compose verifies plan and review hashes through recreation and
  backup/restore; readiness output is private-value free.
- M6H-01 and M6H-02 are merged. Manual acceptance and participant work remain
  separate.

## M6B-GOV-AUDIT implementation

- The static audit covers exactly 383 packages and 1,151 actions, with one
  deterministic row for each stable ID.
- It inventories all 27 domains, 37 mapped levers, used protocol families,
  all risk classes, used evidence kinds, sources, gaps, reviews, and every
  active package.
- It retains stable objective findings and creates a prioritized review queue
  without reading participant or owner-private records.
- Every package is score active by owner direction, while zero packages are
  source complete. Activation is explicitly not treated as governance
  acceptance.
- `ER-M6A-003` remains pending with no completed role, date, or decision;
  `RG-M6A-002` remains open; M6B acceptance remains false.

## Pending owner audit

M6F implements the owner's explicit all-active direction before the consolidated
383/383 content audit. Pending semantic, source, originality, accessibility,
privacy, safety, cultural, specialist, and participant review must remain
visible and must not be represented as clinical, psychometric, cultural, or
intervention-effectiveness validation. Runtime and scoring activation do not
authorize release, deployment, or broader production claims.
