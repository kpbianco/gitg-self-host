# Current state

Last updated: 2026-08-26
Implementation branch: `codex/m6e-full-competency-frontier`

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
```

## Pending owner audit

M6F implements the owner's explicit all-active direction before the consolidated
383/383 content audit. Pending semantic, source, originality, accessibility,
privacy, safety, cultural, specialist, and participant review must remain
visible and must not be represented as clinical, psychometric, cultural, or
intervention-effectiveness validation. Runtime and scoring activation do not
authorize release, deployment, or broader production claims.
