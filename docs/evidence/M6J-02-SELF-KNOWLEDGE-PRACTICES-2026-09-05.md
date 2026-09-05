# M6J-02 self-knowledge practices

Baseline: merged PR #52, `e993ad142dee7652c3c029d6b1c75c0cdaf3d298`.
Branch: `codex/m6j-02-self-knowledge`.
Status: implemented; local and hosted verification results are recorded separately.

## Delivered content

All 12 domain 05 practices are individually authored, with 36 action
instructions and 108 explicit observation checks. The catalog has 54 authored
practices and 329 rewrite-pending practices, with 163 tailored action
instructions in total. Human review completion remains zero. Domain 05 was
selected ahead of the previously proposed domain 03; the latter remains next.

| Competency | Bounded exercise and relation to scope |
| --- | --- |
| 05.01 Personal inventory | Nine headings cover strengths, limits, fears, history, advantages, habits, obligations, dependencies and outcomes; a later opportunity tests one claim. |
| 05.02 Narrative identity | One chapter includes agency, help, constraints, uncertainty and change, with no forced heroic or redemptive ending. |
| 05.03 Strengths and fit | Two comparable tasks distinguish capability, effort, support and conditions, then inform a provisional fit recommendation. |
| 05.04 Personality as hypothesis | A label becomes a falsifiable contextual prediction, followed by two observations and a contrasting-capacity attempt. |
| 05.05 Defenses and self-deception | An ordinary explanation is compared with actions and replaced at a natural cue by a narrower honest response. No hidden motive is diagnosed. |
| 05.06 Triggers and patterns | Two manageable occasions identify an early cue; a naturally occurring opportunity tests a smaller alternative. No distress is induced. |
| 05.07 Feedback | A voluntary event-specific exchange separates intention and impact, checks an accurate summary and tests a change. |
| 05.08 Worth beyond performance | A bounded result is separated from dignity, with proportionate responsibility and ordinary care retained. Feelings are not scored. |
| 05.09 Conflicting concerns | Both concerns receive a fair account and a place in a real trial; the review preserves unresolved tradeoffs. |
| 05.10 Humility | Contribution and dependence stay visible while correction, help, praise and absent recognition are rehearsed or encountered, with those evidence levels distinguished. |
| 05.11 Situated identity | A familiar route separates agency from access and institutional conditions, without demographic inference or group generalization. |
| 05.12 Cultural assumptions | A familiar norm is compared with a situated account and tried through respectful clarification; fictional fallback remains unverified cultural evidence. |

Every exercise includes a usable default, setup, burden, adaptation, scope
limit, review and supportive/mixed/contradictory/inconclusive examples. Some
exercises require an actual opportunity or willing person; unavailable live
work is not silently replaced by claimed behavioral evidence. Sensitive
working notes remain outside structured check-ins. None is therapy, an
identity diagnosis, a mastery measure or an empirical intervention claim.

Two inspected primary research sources support narrowly paraphrased findings:
[Vazire (2010)](https://www.simine.com/docs/Vazire_JPSP_2010.pdf) on differences
between self and other judgment, and
[Fleeson (2001)](https://simine.com/407/readings/Fleeson_2001.pdf) on variation
in personality states. Their registered limitations distinguish these findings
from validity of any person's feedback or effectiveness of these exercises.
The remaining exercise design is original product judgment grounded in the
canonical competency scopes, not presented as newly established science.

## Preserved invariants

A comparison with the baseline found exactly 05.01–05.12 changed among the
383 practice packages. The other 371 packages, including all 42 earlier
authored practices, remain unchanged. All protocol/action IDs, parents and
completion rules remain exact. Assessment, scoring, ranking, activation,
migrations and runtime Python files are unchanged. New observations freeze
their revised checks; existing events still replay their own snapshots.
Active/paused practice import protection remains in force.

Canonical content hash:
`0c49208e796ffbe3cbb2b629287311062cd22327faed025c33075613298dee6a`.
The deterministic coverage, risk, originality, governance and scoring reports
were regenerated. Research and specialist gaps remain open; no source,
specialist or empirical acceptance was manufactured by report generation.

## Integration correction

PR #52 merged on 2026-09-05 at 16:07:55 UTC before its replacement PR run
finished. That run's quality and Compose jobs were cancelled, and its
aggregate failed. The fresh main run
[33976905386](https://github.com/tranquilWorks/gitg-self-host/actions/runs/33976905386)
then reported a real mobile overflow at 200% zoom: the recommendation button
and a status label extended beyond the viewport. It passed 14 of 15 browser
journeys and is not all-green integration evidence.

This batch bounds those labels to their containers, allows text wrapping and
lets the status pill shrink. It retains the existing zoom and overflow
assertions and adds a screenshot of that exact state. No test, timeout,
workflow command or aggregate gate is waived or changed.

## Verification

- Ten focused authoring/import/closeout/replay tests passed, including new
  minimum-credit personality and full-credit feedback cases, replay after a
  later content revision and immutable assessment baselines.
- The full-frontier compiler check and its three tests passed.
- Manifest, Ruff formatting/lint, Django checks and migration drift checks
  passed. Changed-file paths were checked against the active batch.
- All practice, governance and composite catalog report freshness checks passed.
- The broader quick suite identified a stale catalog hash in the older M6D
  readiness report and was stopped for correction. Regeneration changed only
  that hash; both affected competency-readiness tests then passed. The full
  446-test non-browser suite remains a required hosted gate, not a local pass.
- Local Playwright cannot launch because Chromium is absent. Docker is also
  unavailable here. Hosted browser/Compose jobs and screenshot review remain
  required; the two new browser cases cover personality and feedback at
  desktop/mobile sizes, bringing the hosted journey count to 17.
- Full hosted CI, final artifact review and merge remain pending at this
  commit. The PR must record exact head/tree, run and final result. No
  participant data, deployment, specialist acceptance or empirical
  validation was produced by this batch.
