# M6I-01 composite assessment and human-closeout scoring evidence

## Claim boundary

This evidence supports an owner-approved, deterministic software architecture
for assessment-derived starting estimates, human-triggered practice closeout,
completion credit, coverage, and recommendation reranking. It does not establish
mastery, direct assessment of all 383 competencies, specialist acceptance,
psychometric validity, clinical status, cultural or accessibility-population
fitness, participant acceptance, longitudinal effectiveness, release approval,
or deployment approval.

- Baseline commit: `0665d35b3c446c27deb1747dc271b14e6ff6e3ab`
- Working branch: `codex/m6i-composite-closeout-scoring`
- Active contract: `M6I-01-COMPOSITE-CLOSEOUT-SCORING`
- Owner architecture decision: Decision 053 and ADR 0013
- Historical replay boundary: `GG-SCORE-STATE-1.0` remains exact and immutable
- New state contract: `GG-COMPOSITE-CLOSEOUT-SCORING-1.0`

## Implemented scoring design

The concise assessment continues to estimate the 37 levers and seven lever
families. It initializes all competency priorities without asking one question
per competency and without awarding earned completion credit.

For each competency and mapped lever, the relationship allocation is:

`0.50 * canonical relationship + 0.50 * equal mapped-lever share`

This keeps every secondary relationship positive while preserving stronger
canonical relevance. The assessment-derived competency starting estimate is:

`0.50 * mapped lever + 0.25 * mapped family + 0.25 * parent domain`

The parent-domain value is calculated from preliminary member estimates before
being used in the final competency value, so the calculation has no cycle.

Check-ins create immutable evidence and have no composite score effect. The
user must explicitly complete actions and then explicitly close the practice.
At the configured minimum, two of three actions or three of four actions, the
closeout grants `0.75` completion credit. Completing every defined action grants
`1.00`. Any future intermediate count is linearly interpolated. Repeated
closeouts use the maximum active credit rather than adding attempts; reversing
an event deterministically rebuilds from the remaining active closeouts.

Lever and family coverage use normalized blended relationship mass. Domain
coverage is the equal mean of member-competency credit. Remaining need is:

`assessment starting need * sqrt(1 - earned coverage)`

Recommendation priority then combines 50 percent mapped-lever, 25 percent
mapped-family, and 25 percent parent-domain remaining need, applies the
competency's own remaining-credit factor, and preserves the existing explicit
context-priority layer. Completion is never labeled as mastery.

## Whole-catalog disposition

| Inventory | Verified result |
|---|---:|
| Lever families | 7 |
| Assessment levers | 37 |
| Curriculum domains | 27 |
| Competencies | 383 |
| Practices | 383 |
| Actions | 1,151 |
| Blended relationship allocations | 1,403 |

| Distribution | Verified result |
|---|---:|
| Competencies with 2 / 3 / 4 / 5 relationships | 10 / 133 / 216 / 24 |
| Three-action practices with minimum 2 | 381 |
| Four-action practices with minimum 3 | 2 |
| Actions with explicit equal completion units | 1,151 |
| Actions with pre-closeout score effect | 0 |
| Practices with human-closeout scoring | 383 |
| Practices using maximum-not-sum repetition | 383 |
| Missing scoring dispositions | 0 |
| Mastery claims | 0 |

The catalog report embeds semantic report hash
`308c29789f56f376dea02839ba005c74225d6d94a82eff8a235f63516feaf25d`.
The complete JSON file SHA-256 is
`8ebc20d27dc38d51e34ab0b5ae34b48b544965c1523132f06792f2cd4f8632b5`.
Its source hashes are:

- canonical model: `6958ccfbe0c0d80b7485ac866a8418578850284b58956f59168429819447dfc5`
- canonical practice content: `9be5d07ef52421c3dcaea0536fd32221a3cfcef01198252f736200e37b3fa42f`
- scoring contract: `7db7fc622e0f3673536257c1be0aebe989a1d8a551ab1ca2fbf5cddbd0f6ec64`
- scoring-contract schema: `5e6c52b0d7e5f770564e1bed60f3fdf20045a3a89939c121549aa13b7ecc0852`

## State, migration, and lifecycle behavior

- Migration `0012_composite_closeout_scoring` preserves every pre-migration
  sprint as legacy and makes new sprints use the composite contract.
- Additive assessment snapshots, closeout events, state rows, and state
  snapshots are immutable and independently replayable.
- Initialization, processing, duplicate replay, stronger and weaker repeats,
  reversal, repair, and assessment-epoch isolation have focused coverage.
- A submitted check-in leaves composite state and snapshot bytes unchanged.
- A two-of-three closeout produces `0.75`; a later three-of-three closeout raises
  that competency to `1.00`; a later weaker repeat cannot reduce or farm credit.
- Owner archive v2 contains the new private scoring records, and deletion handles
  their explicit dependency order while preserving transactional rollback.
- Application startup rebuilds and verifies the additive composite state after
  migration and canonical seed.
- Profile recommendations fail closed if composite state verification fails.

## Automated results

| Check | Result |
|---|---|
| Focused contract, catalog, model, migration, replay, workflow, lifecycle, and deployment tests | Pass |
| Ruff format/check, Django check, and migration-drift check (`make lint`) | Pass |
| Composite whole-catalog and isolated replay readiness | Pass: 383 competencies, 383 practices, 1,151 actions |
| Catalog governance, practice reports, full frontier, curriculum, competency evidence, and pilot gates | Pass |
| `./scripts/agent-verify.sh contract` | Pass |
| `./scripts/agent-verify.sh quick` | Pass: 398 passed, 13 Playwright tests deselected in 33:59 |
| `./scripts/agent-verify.sh full` | Pass: 398 passed, 13 Playwright tests deselected in 32:29, followed by all audit and readiness gates |
| Full operations gate inside the full harness | Pass: 89 owner records, retention disabled, 27 migrations, backup verified |
| Playwright with real Chromium | Environment blocked: expected pinned Chromium executable is absent |
| Docker Compose backup/restore drill | Environment blocked: this runner has no `docker` executable |

The full harness independently passed catalog governance, composite catalog and
replay, pilot, curriculum, competency evidence, context, Personal OS,
context-priority, M6C pilot, M6D authoring, weekly execution, and M6H operations
readiness. Hosted exact-head Playwright, Compose, and aggregate jobs remain
required after publication. Until they pass, this is local software evidence,
not release or deployment approval.

## Governance boundary

- `ER-M6A-003` remains `pending`.
- `RG-M6A-002` remains `open`.
- M6B specialist acceptance remains false.
- Decisions 047, 048, and 049 remain rejected or superseded; this implementation
  does not silently approve them.
- Decision 052 continues to authorize runtime activation, while Decision 053
  supersedes event-level production scoring for new scoring-version sprints.
- Specialist and owner content review may later change scope or milestones
  without rewriting historical assessment, evidence, or score records.

## Publication boundary

This record was generated before publication and does not by itself prove a
commit, push, pull request, merge, release, or deployment. Publication state
must be verified independently against the repository and hosted checks.
