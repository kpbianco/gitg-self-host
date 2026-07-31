---
name: grounded-growth-product-data
description: Implement and verify one approved Grounded Growth product-data batch while preserving canonical IDs, schema and report integrity, evidence/scoring replay, participant privacy, originality, risk/review gates, and human-reviewed target PRs.
---

# Grounded Growth product-data delivery

## Required inputs

- `AGENTS.md`
- `contracts/active-batch.yaml`
- `contracts/verification.yaml`
- `docs/CURRENT_STATE.md` and `docs/HANDOFF.md`
- `docs/PROJECT_HANDOFF.md`, `docs/PRODUCT_DECISIONS.md`, M6 program documents
- canonical release manifest, packages, registries, schemas, reports, fixtures
- current source, migrations, CI, branch, diff, and retained evidence

## Procedure

1. Confirm exact `main`, active batch, stable-ID cohort, and working-tree state.
2. Map every acceptance item to canonical source, runtime ownership, migration,
   deterministic report, fixture/replay, browser/deployment gate, and manual
   review.
3. Preserve unrelated work and every forbidden path. Do not let generated
   reports become competing editable source.
4. For context/scoring work, preserve immutable baselines, historical evidence,
   assessment epochs, one-way contribution, reversal, and explicit activation.
5. For content work, inspect each exact competency and individually author
   purpose, applicability/N-A, intervention, actions, burden, adaptations,
   privacy, stop/escalation, evidence, contradiction/adverse, completion,
   transfer, mastery, sources, risk, review, and score disposition.
6. Use current primary/systematic/official/professional sources where needed;
   record retrieval date, claim classification, limitations, and unresolved
   gaps. Never treat search output as specialist validation.
7. Regenerate and review coverage, domain/lever, risk, source, originality,
   typed-capability, scoring-policy, and readiness artifacts relevant to the
   change.
8. Add exact positive/negative/property/replay/migration/browser tests and run
   focused checks followed by `./scripts/agent-verify.sh full`.
9. Update `MANIFEST.tsv` with `./scripts/verify-manifest.py --write`, rerun the
   verifier, and create retained batch evidence.
10. Inspect the entire diff for stable IDs, boilerplate, copy drift, privacy,
    score activation, claims, migrations, and rollback.

## Stop conditions

Stop instead of improvising when:

- M6B specialist governance or another explicit review gate is incomplete;
- the selected stable-ID cohort must change;
- source, risk, accessibility, privacy/safety, or qualified review is missing for
  a claim the batch would otherwise make;
- a generated package is generic, substantially duplicated, or not executable;
- score activation, assessment/scoring math, immutable history, or participant
  data boundaries would change outside the approved batch;
- deterministic reports/replay/Compose/browser gates cannot be made credible;
- product doctrine or a material context/ranking decision is unresolved.

## Evidence and exit criteria

Every acceptance item is pass, fail, blocked, or unverified with exact commands,
hashes, reports, fixtures, migrations, and validation level. Coverage and
software readiness are never described as mastery or external validity. The
branch is ready for a human-reviewed draft PR; the agent does not merge it.
