# M6B-GOV-AUDIT evidence — 2026-09-01

## Objective

Produce the deterministic, finding-complete software audit and prioritized
review packet for all 383 canonical packages and 1,151 stable actions. Preserve
every owner-directed activation record while keeping specialist and owner
acceptance separate and explicitly pending.

## Exclusions

This batch does not perform or claim semantic, cultural, accessibility-
population, privacy/safety, measurement, legal, clinical, psychometric,
participant, longitudinal, release, deployment, mastery, or intervention-
effectiveness acceptance. It changes no package, action, evidence rule,
scoring rule, activation entry, database model, migration, UI, or participant
state.

## Deterministic audit result

| Inventory | Result |
| --- | ---: |
| Package rows | 383 |
| Action rows | 1,151 |
| Legacy packages | 5 |
| Typed packages | 378 |
| Generated additions | 374 |
| Domains | 27 |
| Parent-mapped levers | 37 |
| Used protocol families | 11 |
| Risk classes | 3 |
| Used evidence kinds, including legacy markers | 9 |
| Score-active packages | 383 |
| Source-complete packages | 0 |
| Retained open findings | 3,369 |

The current findings contain 1,045 high, 2,073 moderate, and 251 low
review items. There are no unresolved critical objective structural findings.
All 383 packages have exact/normalized duplicate-review candidates because the
catalog deliberately retains shared structural and boundary language; 154
packages participate in one or more bounded near-duplicate candidates. These
signals route review and do not establish semantic duplication or originality.

## Governance boundary

- `ER-M6A-003` remains `pending`.
- Its completed-role list remains empty, with no completion date or decision
  reference.
- `RG-M6A-002` remains `open`.
- M6B acceptance remains false and requires the separate manual `M6B-GOV`
  contract.
- All 383 packages remain owner-directed runtime and score active. The audit
  explicitly does not treat activation as source completeness, safety,
  accessibility, cultural fit, measurement validity, effectiveness, or
  specialist acceptance.

## Artifacts

- `reports/practice-content/catalog_governance_audit_v1.json`
- `reports/practice-content/catalog_governance_findings_v1.csv`
- `reports/practice-content/catalog_governance_review_queue_v1.csv`
- `reports/practice-content/catalog_governance_review_packet_v1.md`
- `contracts/catalog-governance-audit.schema.json`

The JSON contains every package and action row plus complete inventories. The
finding CSV retains stable IDs, severity, objective evidence, affected stable
IDs, remediation class, status, and required roles. The review queue adds
priority, risk, domain, family, evidence-kind, and dependency routing. The
Markdown packet summarizes the queue without catalog prose or participant and
owner-private values.

## Validation

Completed during implementation:

- `python scripts/catalog_governance_audit.py` — PASS; four reports generated.
- `python scripts/catalog_governance_audit.py --check` — PASS; byte-stable.
- focused audit tests — PASS; 6 passed in 52.17 seconds.
- Ruff formatting and static checks for the audit implementation — PASS.
- `./scripts/agent-verify.sh contract` — PASS; manifest, formatting, Ruff,
  Django configuration, and migration-drift checks passed.
- `./scripts/agent-verify.sh quick` — PASS; 375 passed, 13 deselected in
  32 minutes 19 seconds.
- `./scripts/agent-verify.sh full` — PASS; 375 passed, 13 deselected in
  32 minutes 23 seconds, followed by the audit, pilot, curriculum,
  competency-evidence, context, Personal OS, context-priority, M6C, M6D,
  weekly-execution, and operations readiness gates.
- `make full-frontier-check` — PASS; deterministic 383/383 authored coverage
  and 3 focused tests passed.
- `make practice-report-check` — PASS; reports current.
- `make e2e` — ENVIRONMENT BLOCKED before application execution because the
  pinned Chromium binary is absent. Installing it was attempted, but the
  restricted runner could not download from Playwright's CDN (timeouts/502).
- `make compose-smoke` — ENVIRONMENT BLOCKED before repository execution
  because this runner has no `docker` executable.

The exact-head Playwright and Compose jobs therefore remain required in hosted
CI after publication. Until those jobs pass, this evidence remains partial. It
is always a software-audit implementation record, not a completed human
governance decision.

## Residual risks

- Lexical similarity can route review but cannot establish semantic
  originality, correctness, or intervention fit.
- Valid source metadata does not establish claim-level external source
  completeness; all 383 packages remain incomplete at that gate.
- Owner-directed activation precedes consolidated review and therefore remains
  a high-priority governance boundary for every package.
- The reviewer queue is intentionally large and must not be bulk-accepted
  without actual role-specific review records.
