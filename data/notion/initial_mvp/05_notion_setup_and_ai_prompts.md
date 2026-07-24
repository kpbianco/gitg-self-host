# Notion setup — Grounded Growth MVP

## Why this version is intentionally simple

This first Notion build uses two independent databases:

1. **Lever Baselines** — the 37 starting developmental scores.
2. **Development Tasks** — all 383 master competencies, with the baseline mastery and priority already calculated.

The task database is statically ranked from the imported baseline. The databases are not dynamically related yet. This avoids a large Task–Lever join database and manual relation setup before the workflow has been validated.

## Import order

1. Create a page named **Grounded Growth**.
2. Import `04_starting_profile_page.md` into that page or paste its contents.
3. Create the **Lever Baselines** database using Prompt A below, then use `••• → Merge with CSV` and select `01_lever_baselines_import.csv`.
4. Create the **Development Tasks** database using Prompt B below, then merge `02_development_tasks_ranked_import.csv`.
5. Optionally create an **Orientation Profile** database and import `03_orientation_profile_import.csv`, or keep that information only on the profile page.
6. Add linked views of Development Tasks to the Grounded Growth page.

## Prompt A — Lever Baselines database

Create a full-page database named “Lever Baselines”. Use “Lever” as the title property. Add these properties with these types:
- Lever ID — text
- Family — select
- Raw Self-Report — number formatted as percent
- Baseline Mastery — number formatted as percent
- Evidence Confidence — number formatted as percent
- Need Score — number formatted as percent
- Need Rank — number
- Definition — text
- Assessment Version — text
- Baseline Date — date
- Notes — text

Create these views:
1. “Greatest Need” — table sorted by Need Rank ascending; show Lever, Baseline Mastery, Evidence Confidence, Need Score, and Family.
2. “By Family” — board or table grouped by Family and sorted by Need Score descending.
3. “Low Confidence” — table filtered to Evidence Confidence below 0.45 and sorted ascending.

Do not add example rows because I will merge a CSV into the database.

## Prompt B — Development Tasks database

Create a full-page database named “Development Tasks”. Use “Task” as the title property. Add these properties with these types:
- Task ID — text
- Rank — number
- Priority Band — select
- Priority Score — number formatted as percent
- Baseline Mastery — number formatted as percent
- Raw Self-Report — number formatted as percent
- Evidence Confidence — number formatted as percent
- Status — status with Not started, In progress, Complete, and Skip
- Current Focus — checkbox
- Domain — select
- Primary Lever — select
- Primary Lever ID — text
- Primary Lever Weight — number formatted as percent
- Lever Mapping — text
- Scope — text
- Evidence of Progress — text
- Applicability — select
- Normative Status — select
- Formation Modes — multi-select
- Evidence Types — multi-select
- Professional Boundary — text
- Task Level — select
- Journal Prompt — text

Create these views:
1. “Current Queue” — table filtered to Status is not Complete and Status is not Skip; sort Priority Score descending. Show Rank, Task, Priority Score, Baseline Mastery, Evidence Confidence, Domain, Primary Lever, and Status.
2. “Top 25” — same filters plus Priority Band is Top 25; sort Rank ascending.
3. “By Domain” — board grouped by Domain; filter Status is not Complete and Status is not Skip.
4. “Low Confidence” — table filtered to Evidence Confidence below 0.45; sort Priority Score descending.
5. “In Progress” — table filtered to Status is In progress or Current Focus is checked.
6. “Completed” — table filtered to Status is Complete; sort Rank ascending.

Do not add example rows because I will merge a CSV into the database.

## Recommended dashboard layout

At the top of the Grounded Growth page, keep the starting-profile summary. Below it add:

- A linked **Top 25** view of Development Tasks.
- A linked **Greatest Need** view of Lever Baselines.
- A linked **In Progress** view.
- A short callout: “The ranking proposes where evidence suggests attention may be valuable. Applicability, safety, role, timing, and informed judgment always override rank.”

## Manual property cleanup after CSV merge

CSV import may initially treat some properties as text. Confirm:

- Baseline Mastery, Raw Self-Report, Evidence Confidence, Need Score, Priority Score, and Primary Lever Weight are Numbers formatted as Percent.
- Current Focus is Checkbox.
- Status is Status.
- Baseline Date is Date.
- Formation Modes and Evidence Types are Multi-select if useful; leaving them as text is acceptable for V1.

## Current design boundary

The Lever Baselines database is the reference source for the starting scores, but editing it will not automatically rerank Development Tasks in this V1. The task ranking was calculated when the CSV was generated. A later normalized version can use Tasks, Levers, and Task–Lever Links databases with relations and rollups.
