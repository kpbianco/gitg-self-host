# Delivery automation

## Deterministic authority

The target repository's Verification workflow remains authoritative:

1. Ruff, Django check, pytest, pilot readiness, curriculum readiness, and
   competency-evidence readiness.
2. Playwright core journeys with retained diagnostics.
3. Docker Compose deployment, migration, login, persistence, backup/restore,
   recreation, and shutdown drill.
4. Aggregate Pilot readiness gate over the same commit.

The local harness runs static/migration/manifest, non-E2E tests, and all three
readiness contracts. It does not represent local absence of Playwright or Docker
as a pass; GitHub CI remains required.

## Autopilot workflow

For each non-gate batch:

1. Inspect current target `main` and coverage/review state.
2. Generate and schema-validate the canonical control-plane contract.
3. Auto-merge only that control contract after its checks pass.
4. Activate the exact contract on an isolated target branch.
5. Run implementation and independent system-risk audit Codex turns.
6. Run local full verification and at most two scoped repairs.
7. Require retained evidence and allowed-path audit.
8. Commit, push, and open a draft target PR.
9. Wait for CI and attempt at most two scoped repairs.
10. Stop for owner review; never ready or merge the target PR.

## Dynamic content queue

After M6D-03, the runner reads
`reports/practice-content/competency_coverage_v1.csv`, groups canonical rows by
domain and fixed position, and creates stable approximately 12-ID cohorts. The
contract and implementation prompt name every ID. Existing reviewed packages are
preserved and only uncovered rows are eligible.

## Permissions and limits

- Filesystem: target/control workspace only.
- Shell network: disabled in Codex sandbox.
- Web-search tool: enabled for current source discovery.
- Target merge: forbidden.
- Control contract auto-merge: green deterministic checks only.
- Repair attempts: two.
- Force push, release, deploy, secret/settings changes: forbidden.
- Specialist, participant, production activation, and manual release gates:
  cannot be waived.

## Rollback and audit

Installer backups are timestamped. Every run writes local logs below sibling
`.portfolio-autopilot/logs/gitg-self-host/`. Target evidence is committed under
`docs/evidence/`. Revert one batch PR or restore a verified database backup; do
not rewrite immutable history to hide a bad batch.
