# Canonical practice content

## Release root

`data/practices/release_manifest.yaml` is the only entry point for canonical
practice content. It declares:

- `GG-PRACTICE-RELEASE-1.0`;
- the exact package paths included in the release;
- every schema, registry, and governance input covered by the content hash;
- the independent catalog content hash;
- the frozen `GG-PRACTICE-RUNTIME-PROJECTION-1.0` hash.

The loader rejects missing, duplicate, unlisted, absolute, traversing, or
misplaced package paths. All schemas are local Draft 2020-12 JSON Schemas; no
network lookup is required.

## Package sections

| Section | Contents |
|---|---|
| Identity | Content and protocol versions, stable ID, slug, name, parent competency, domain |
| Governance | Availability, editorial and scoring status, risk, policy, fingerprinted sources, typed review state, linked gaps/reviews, frozen compatibility exceptions, deprecation |
| Meaning and fit | Purpose, recommendation reason, classified claims, applicability, N/A behavior, readiness, opportunity, prerequisites, alternatives, role/pathway/worldview conditions |
| Intervention | Family, duration, cadence, setup, privacy, burden, normally 3–5 sequenced actions, bounded due windows, adaptations, stop and escalation conditions |
| Evidence and scoring | Accepted evidence, runtime observation version, check-in fields, adverse indicators, independence/context/repetition/recency rules, rubrics, eligibility, allocation, minimum evidence, withholding |
| Completion and review | Completion rules, mastery disclaimer, progression, transfer limit, individualized reflection, repeat/adapt/stop/escalate guidance, four evidence-direction examples |
| Presentation | Existing setup copy, source-only labels for every check-in field, completion copy, plain-language evidence explanation, display order |

M6A packages are `projected_legacy`: their runtime fields exactly preserve the
five reviewed protocols while additive metadata makes gaps explicit.

## Registries

- `source_registry.yaml` distinguishes empirical findings, public or
  professional standards, normative positions, cross-tradition synthesis,
  product-design judgments, and safety precautions. Internal repository
  sources are marked `design_only` or `limited`, not disguised as intervention
  validation. Repository locators must exist and match their recorded SHA-256;
  claim classifications and applicability validate in both directions.
- `risk_taxonomy.yaml` defines low, moderate, and high-risk release gates,
  reviewer roles, sensitive-data limits, and pre-review scoring ceilings.
- `scoring_policy_registry.yaml` defines structured-self-report eligibility,
  corroboration, artifact/objective, qualified-evidence, shadow-only, and
  non-scored reflection policies. N/A uses the cross-cutting
  `N-A-NO-DEFICIT` disposition.
- `protocol_families.yaml` supports twelve intervention shapes rather than
  forcing every competency into a ten-day three-action sprint.
- `activation_ledger.yaml` is the only source of runtime score activation.

Open source questions are in `research_gaps.yaml`; specialist work is in
`expert_review_queue.yaml`.

## Projection and version boundaries

The importer validates both the existing curriculum/model/mapping bundle and
the practice release before writes. It then projects only existing
`PracticeProtocol` and `PracticeAction` fields.

The old curriculum source hash remains:

```text
6958ccfbe0c0d80b7485ac866a8418578850284b58956f59168429819447dfc5
```

The frozen runtime projection remains:

```text
274f7244630ed56d56a443a6a699399edade6c67fcf964237559e05b72368e35
```

The catalog has a separate release hash because adding editorial metadata must
not make an existing assessment curriculum version appear to change.

M6A does not execute the richer future evidence fields. All five projections
retain `practice-observation-v1`; a typed contract and direct competency
evidence belong to M6B.

## Generated control reports

`python manage.py generate_practice_reports` deterministically writes:

- `competency_coverage_v1.csv` — all 383 competencies and their package,
  review, policy, activation, mapping, and blocker state;
- `domain_coverage_v1.csv` and `lever_coverage_v1.csv`;
- `risk_register_v1.csv`;
- `coverage_summary_v1.json`;
- `content_originality_v1.json`.

The reports contain no generated timestamp. `--check` recomputes exact bytes
and fails when a committed report is absent or stale.

The originality report detects exact/normalized substantive duplicates,
near-duplicate candidates, repeated reflection sets, duplicate action
instructions and evidence rules, and suspicious duration/action-count
uniformity. Every human-authored meaning, intervention, action, evidence,
reflection, completion, safety, and presentation field is included. Only
exact, hash-pinned language from the frozen five-protocol architecture is
classified as approved shared content; copied future text is
`review_required`. The two duplicate legacy evidence-rule groups are tied to
explicit exception IDs.

## Commands

```bash
make practice-reports
make practice-report-check
make curriculum-check
```

`make curriculum-check` uses a disposable database and runs
`GG-CURRICULUM-EXPANSION-READINESS-1.0`. The additive verifier calls the
unchanged `GG-PILOT-READINESS-1.0`, checks current reports, validates exact
coverage counts, and compares canonical projections with the seeded runtime.
