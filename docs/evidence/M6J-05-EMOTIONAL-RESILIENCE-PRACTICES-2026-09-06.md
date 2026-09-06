# M6J-05: emotional maturity, resilience and mental well-being

Baseline: stacked M6J-04 content at
`0a3939a468dac1e9ffd9451c012968e88840930c`.

## Authored content

All 14 competencies in domain 07 now have individually written,
self-contained exercises. They add 42 distinct action instructions, 168
observable checks and 56 supportive, mixed, contradictory or inconclusive
outcome examples. Cumulative tailored coverage is **105/383**, leaving
exactly **278 rewrite-pending** and zero automatically marked human-review
complete.

The exercises produce concrete outcomes rather than asking a participant to
invent an intervention: an emotion-differentiation record, early body-signal
cue, cue–pause–return card, repeated low-stakes approach, anger repair,
loss/remembrance action, shame-to-repair record, comparison conversion,
consented emotional disclosure, accountable-care restart, hard-fact/hope
plan, post-setback experiment, verified help-route card and cross-context
regulation menu.

`docs/authoring/exercises/07.yaml` is the complete authored input.
`docs/authoring/M6J-05-PRACTICE-READER.md` supplies a compact review index,
and `docs/authoring/M6J-05-SCOPE-MAP.md` traces every canonical scope facet to
the actual actions and limits. The compiler projects the exact authored fields
into the manifest-listed canonical runtime packages; it does not infer content
from labels, personality or a noun-substitution template.

## Safety and claim boundaries

This high-risk domain remains educational and developmental. It introduces no
diagnosis, treatment, unsupervised clinical exposure, trauma provocation,
deliberately induced dysregulation, medication change, unsafe confrontation or
delay before urgent help. The 07.04 exercise uses a supplied ordinary
meeting-question case and explicitly excludes trauma, OCD, panic, phobias,
unsafe people and clinically significant fear from self-guided exposure. The
07.13 support card must use the participant's current location and requires a
real contact rather than a rehearsal when a current threshold is present.

Two inspected NIMH pages were added. `Psychotherapies` supports only the
distinction between clinician-delivered exposure therapy and the product's
low-stakes approach exercise. `Caring for Your Mental Health` supports a
limited help-seeking and functioning boundary. Existing NIMH help-route and
NHS grief sources now also apply to 07.13 and 07.06 respectively. The source
registry records access date, exact supported claim and limitations. None of
these sources validates the product-authored exercise or determines an
individual's diagnosis or treatment need.

## Preserved invariants

An exact comparison with the M6J-04 baseline confirmed:

- all 14 changed packages are in `data/practices/protocols/07/`;
- the other 369 protocol packages are byte-identical;
- all 14 stable protocol IDs, their 42 action IDs, parent competency IDs and
  completion rules are unchanged;
- the complete catalog remains 383 protocols and 1,151 actions;
- activation, assessment, ranking, scoring mathematics and explicit human
  closeout are unchanged;
- active/paused import protection and immutable event-snapshot replay remain
  in the focused regression suite;
- 13.02 retains its frozen typed evidence rules and the legacy runtime
  compatibility boundary is untouched.

Canonical content hash:
`77d344187c97c95c67a23ca4b186e22efe6e716c4e8076f738ebfbfd95a2fcc7`.

## Local verification

- The 14 authoring records parsed as YAML and passed an explicit field,
  canonical-ID, string-length, action-count, check-count and instruction-
  uniqueness audit: 14 exercises, 42 actions and 168 checks.
- Full-frontier generation and its deterministic `--check` pass reported
  105/383 authored and 278 remaining.
- Practice coverage, risk and originality report generation completed; their
  freshness check passed.
- Catalog-governance generation completed; its subsequent check reported
  `verified changed=0`.
- The composite catalog check reported 383 competencies, 1,151 actions and no
  missing scoring dispositions.
- The competency-evidence report freshness check passed.
- Ruff 0.14.2 formatting and lint passed; Django 6.0.7 system and migration-
  drift checks passed; Python compilation of the changed tests passed.
- `MANIFEST.tsv` verifies 902 intended files.
- `git diff --check`, the changed-package boundary check and the explicit
  ID/action/completion comparison passed.
- All four new browser cases' expected scope, example, source and action-
  scoped observation text were checked against the runtime projection.
- The focused authoring/import/closeout/replay suite passed **23 tests in
  203.77 seconds**, including four new domain 07 closeout/replay cases.

The workspace did not contain the repository's packaged development
environment and its package-index request was unavailable. Local checks used
source checkouts of the pinned-compatible Django/pytest dependencies and a
temporary JSON-Schema compatibility validator after a separate explicit audit
of this batch's authoring contract. This is useful local execution evidence,
but it is not represented as equivalent to CI's actual `jsonschema`, Ruff,
Playwright or Compose environment.

## Required hosted verification

Hosted CI must still run the real dependency lock range, complete schema and
manifest checks, full non-browser suite, all readiness contracts, Playwright
journeys, Compose backup/restore/recreation and the aggregate Pilot readiness
gate. Four new browser cases cover emotion differentiation, graduated
approach, consented expression and help-route preparation at mobile and
desktop widths. Local browser execution and visual artifact review are not
claimed, and Docker is unavailable in this workspace.

## Remaining work

The 278 other competencies remain explicitly rewrite-pending. Domain 08 is
next, but it contains two legacy practices whose runtime compatibility needs
an explicit disposition before their guides are enriched. Specialist,
clinical, accessibility, cultural, source-completeness and empirical review
remain open. `ER-M6A-003`, `RG-M6A-002` and all eight participant evidence axes
remain open. Completion is never represented as mastery or human worth.
