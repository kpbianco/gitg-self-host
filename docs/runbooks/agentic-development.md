# Agentic development runbook

## Install and verify

```bash
./scripts/agent-verify.sh contract
./scripts/agent-verify.sh quick
./scripts/agent-verify.sh full
```

Playwright, Compose, and the aggregate Pilot readiness gate must still pass on
GitHub for every target PR.

## Run the governed queue

```bash
./scripts/roadmap-autopilot.sh
```

The current run stops at `M6B-GOV`. After the actual specialist and owner records
are completed:

```bash
export GITG_M6B_SPECIALIST_REVIEW_COMPLETE=1
export GITG_M6B_OWNER_ACCEPTED=1
./scripts/roadmap-autopilot.sh --allow-manual
```

The runner then generates/merges missing control contracts, implements the next
target batch, verifies and repairs it, and opens a draft target PR. Review and
merge that PR manually, then rerun the same command for the next batch. No new
feature prompt is needed.

## Resume

Rerun after interruption, credit exhaustion, failed local verification, or a CI
repair. The state machine reuses the current batch branch and PR.

## Review checklist

- exact stable IDs and canonical sources;
- no generic or duplicated intervention copy;
- source, risk, review, research-gap, scoring, and activation records;
- deterministic report/hash freshness;
- migration/replay/backup behavior;
- privacy and export boundaries;
- no hidden context defaults or score activation;
- evidence level and unsupported claims;
- complete local and GitHub gates.

## Merge boundary

The autopilot never marks a Grounded Growth target PR ready or merges it. The
owner reviews retained artifacts and performs the merge through GitHub.
