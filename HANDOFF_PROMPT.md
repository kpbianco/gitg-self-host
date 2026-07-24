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

Your task is **Milestone 1 only**: build a self-hosted guided-practice UX with static scores. Do not enable dynamic mastery/confidence mutation.

Use the technical and UX constraints in `AGENTS.md`. The desired default stack is Next.js + TypeScript, SQLite + Drizzle, Zod, Tailwind, Vitest, Playwright, Dockerfile, and Docker Compose. You may propose a materially simpler equivalent, but explain and receive approval before deviating.

Implement:
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
2. Propose a concise architecture and milestone plan.
3. Identify data inconsistencies or missing canonical inputs.
4. Do not ask me to restate background already in the repository.

Then implement in reviewable batches. For each batch:
- run format/lint/typecheck/unit/E2E tests;
- audit against the product doctrine;
- report exact passes/failures;
- open a PR and ask me to approve it.

Do not implement M2 evidence scoring or M3 dynamic scoring unless I explicitly authorize the next milestone after reviewing M1.

---
