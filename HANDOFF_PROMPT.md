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
owner. M1A is a review gate: if its pull request has not been approved and
merged, do not begin M1B. Do not enable dynamic mastery/confidence mutation.

Use the binding stack in `AGENTS.md`: a Python/Django monolith with Django
templates, local assets, SQLite, Gunicorn, pytest, Ruff, Playwright, Dockerfile,
and one Docker Compose application service. The earlier Next.js suggestion is
superseded by ADR 0001. Do not add a Node.js runtime server.

After M1A approval, and only when M1B is explicitly authorized, implement:
- curriculum/profile import with stable IDs and version metadata;
- concise home page;
- profile page explaining raw/calibrated/confidence;
- practice recommendation page;
- setup wizard;
- active practice page;
- under-two-minute evidence check-in;
- pause/resume;
- final review;
- static score-impact preview only;
- one complete `Deepen One Existing Friendship` protocol;
- inactive placeholders for the four additional protocols named in `AGENTS.md`.

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

Do not implement M2 evidence scoring or M3 dynamic scoring unless I explicitly authorize the next milestone after reviewing M1.

---
