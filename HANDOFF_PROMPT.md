# Codex / Work Tab Handoff Prompt

Use the following prompt in the new GitHub-connected Work/Codex session:

---

You are taking over development of Grounded Growth in `kpbianco/gitg-self-host`.

Start by reading, in order:
1. `AGENTS.md`
2. `docs/PROJECT_HANDOFF.md`
3. `docs/PRODUCT_DECISIONS.md`
4. `docs/pilot/PILOT_002_FINDINGS.md`
5. `docs/SCORING_DESIGN.md`
6. `MANIFEST.tsv`

Then inspect the canonical data under:
- `data/curriculum/`
- `data/model/`
- `data/assessment/`
- `data/notion/`

Treat `legacy/` as provenance only. Do not build implementation behavior from legacy notes when canonical files disagree.

Work only on the milestone batch explicitly authorized by the repository
owner. M1A and M1B are merged. M2A is the bounded evidence-contract batch in
`docs/evidence-contract.md` and remains a review gate. Do not begin M3 or
enable dynamic mastery/confidence mutation.

Use the binding stack in `AGENTS.md`: a Python/Django monolith with Django
templates, local assets, SQLite, Gunicorn, pytest, Ruff, Playwright, Dockerfile,
and one Docker Compose application service. The earlier Next.js suggestion is
superseded by ADR 0001. Do not add a Node.js runtime server.

The implemented M1 boundary includes:

- canonical curriculum/profile import with stable IDs and version metadata;
- assessment v1.1 taking plus GGA11/GGA1 import;
- concise home/profile and recommendation explanation;
- seven-step setup, active practice, compact draft/submitted check-ins;
- active/paused/stopped/completed states and final review;
- one complete `Deepen One Existing Friendship` protocol;
- inactive placeholders for the four additional protocols in `AGENTS.md`;
- no score mutation.

The M2A boundary adds immutable, replayable `GG-EVIDENCE-1.0` events and
conservative M1 backfill. It stops before task-to-lever allocation, posterior
updates, score snapshots, and dynamic recommendations.

Acceptance criteria are in `docs/PROJECT_HANDOFF.md`. Add automated tests for every testable criterion. The app must run through Docker Compose.

Before changing code:
1. Audit the repository and data package.
2. Confirm the accepted architecture and make a concise batch plan.
3. Identify data inconsistencies or missing canonical inputs.
4. Do not ask me to restate background already in the repository.

Then implement in reviewable batches. For each batch:
- run Ruff, Django checks, pytest, and applicable Playwright tests;
- audit against the product doctrine;
- report exact passes/failures;
- open a PR and ask me to approve it.

Do not implement M3 dynamic scoring unless I explicitly authorize the next
milestone after reviewing M2A.

---
