# M6E full competency frontier evidence

Date: 2026-08-26

Baseline: `main@5a120ddac38db68e0a529b5a687836d61bee4889`

Batch: `M6E-FULL-FRONTIER`

## Delivered source frontier

| Measure | Result |
| --- | ---: |
| Canonical competencies | 383 |
| Authored packages | 383 |
| Uncovered competencies | 0 |
| Domains with authored packages | 27/27 |
| Parent-mapped levers covered | 37/37 |
| Recommendation-target levers covered | 37/37 |
| Preserved prior packages | 9 |
| Generated packages | 374 |
| Source actions | 1,151 |
| Generated actions | 1,122 |
| Runtime protocols/actions | 5/15 |
| Score-active protocols | 1 (`PRACTICE-FRIENDSHIP-01`) |
| Release candidates | 0 |
| Source-complete packages | 0 |

Catalog content hash:
`fb4b29d447232034b069b24871cc4eca77b951b9440e6ed1a2994283db5c04b7`

## Risk and scoring disposition

| Risk class | Packages | Scoring disposition |
| --- | ---: | --- |
| `RISK-HIGH` | 132 | `SP-NON-SCORED-REFLECTION` |
| `RISK-MODERATE` | 137 | `SP-SHADOW-ONLY` except preserved packages under their existing exact disposition |
| `RISK-LOW` | 114 | `SP-SHADOW-ONLY` except preserved friendship under its existing exact disposition |

All 374 generated packages are editorial drafts, inactive, unprojected, and
without an approved activation contract. No generated package is score-active.

## Originality controls

The deterministic originality report records:

- zero exact duplicate action-title groups;
- zero exact duplicate action-instruction groups;
- zero exact duplicate reflection-set groups;
- two frozen legacy evidence-rule-payload duplicate groups;
- bounded near-duplicate inventories retained for human review rather than
  represented as semantic approval.

The 383-row legacy Notion source remains provenance only. Its repeated journal
prompt is not used as generated protocol content.

## Deterministic authoring

`scripts/author_full_competency_frontier.py` preserves the nine prior packages
byte-for-byte and derives every other package from the canonical competency
identity, scope, evidence target, classification, domain boundary, and complete
parent mapping. `--check` validates the expected YAML, registries, release
manifest, and catalog hash without rewriting files.

Focused tests assert one-to-one competency coverage, deterministic stable IDs,
unique generated actions, risk-to-scoring disposition, inactive activation,
complete lever coverage, valid target subsets, and the frozen runtime.

## Validation record

| Command | Result |
| --- | --- |
| `scripts/author_full_competency_frontier.py --check` | passed; 383/383 current |
| `manage.py generate_practice_reports` | passed; reports regenerated |
| focused full-frontier identity/runtime test | passed |
| complete focused frontier/report suite | passed; 3 tests |
| complete non-browser pytest suite | passed; 346 tests, 11 browser tests deselected |
| competency-evidence report generation/check | passed |
| curriculum, competency-evidence, and M6D readiness | passed |
| `scripts/agent-verify.sh quick` | passed; retained local log |
| `scripts/agent-verify.sh full` | passed; retained local log, including a second 346-test run and all readiness contracts |
| Playwright browser journeys | environment-unavailable; all 11 selected tests reached setup, but no Chromium binary was installed and every Playwright CDN mirror returned a zero-byte archive |
| Docker Compose smoke | environment-unavailable; the `docker` executable is not installed |
| hosted CI | pending candidate push |

The browser and Compose limitations are local environment availability, not
test failures in application behavior. Hosted CI remains the required
candidate-commit execution path for those checks.

## Validation performance

At 383 packages, the prior loader recompiled and self-validated the identical
protocol JSON Schema once per YAML file. The loader now caches compiled schemas
by path, mtime, and size, and caches a validated catalog by a SHA-256
fingerprint of every canonical practice input and repository-backed source.
Each caller receives a deep copy. A focused regression test proves caller
mutation cannot contaminate later loads and post-cache source drift still
invalidates the cache and fails closed.

## Claim boundary and deferred audit

This evidence establishes deterministic source authoring, schema validity,
one-to-one coverage, mapping validity, static risk/scoring dispositions,
duplicate detection, and regression boundaries. It does not establish semantic
quality, source completeness, cultural or accessibility adequacy, clinical or
psychometric validity, intervention effectiveness, specialist approval,
participant validation, release readiness, deployment readiness, production
fitness, or mastery.

Human semantic, source, originality, accessibility, privacy, safety, cultural,
and specialist review is explicitly pending for the owner's consolidated
383/383 audit. `ER-M6A-003` remains pending, `RG-M6A-002` remains open, and
Decisions 047–049 remain proposed.
