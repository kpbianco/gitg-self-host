# Post-M4 Pilot-Readiness Closeout

## Purpose

This closeout freezes and verifies the reviewed initial product boundary before
Grounded Growth is used in a private pilot. It does not add a protocol, change
assessment v1.1, or authorize another score-active practice.

The versioned software contract is `GG-PILOT-READINESS-1.0`.

## Reviewed inventory

| Boundary | Required state |
|---|---:|
| Curriculum domains | 27 |
| Competencies | 383 |
| Lever families | 7 |
| Levers | 37 |
| Orientations | 6 |
| Archetypes | 15 |
| Archetype-to-lever affinities | 555 |
| Competency-to-lever links | 1,403 |
| Practice protocols | 5 |
| Practice actions | 15 |
| Executable protocols | 5 |
| Score-active protocols | 1, friendship only |
| Pilot 002 demonstration profiles | 1 |
| Pilot 002 baselines / orientations / published archetypes | 37 / 6 / 3 |

`python manage.py verify_pilot_readiness` checks this inventory, every stable
protocol/action/parent/target link, the reviewed protocol-configuration
fingerprint, each canonical competency weight, the mastery disclaimer, Pilot
002 completeness, draft/evidence separation, the score-inactive boundary,
evidence replay, and score-state replay. It is read-only and exits nonzero on
drift.

Use an isolated fresh database:

```bash
make pilot-check
```

Verify the running deployment without creating or repairing state:

```bash
docker compose exec app python manage.py verify_pilot_readiness
docker compose exec app python manage.py verify_pilot_readiness --json
```

## Verification gate

Pull requests and `main` have four GitHub Actions jobs:

1. Ruff, Django checks, pytest, and the isolated readiness drill;
2. nine Playwright journeys;
3. the production Docker Compose deployment drill;
4. one aggregate **Pilot readiness gate** that passes only when the other
   three jobs pass.

The browser job retains `playwright-results` for seven days. On a passing run,
the artifact contains desktop and 390-by-844 mobile screenshots of the
reviewed protocol surfaces. On a failure, it also retains Playwright traces
and failure screenshots when available.

Repository branch protection should require **Pilot readiness gate** before a
pilot-bound merge. The workflow can create that check, but repository settings
remain an owner operation.

## Walkthrough matrix

Review the artifact and the live Compose deployment at desktop and mobile
widths. A reviewer should record the commit, date, environment, and any
follow-up issue.

| Surface | Desktop check | Mobile / keyboard check |
|---|---|---|
| Login and home | Calm hierarchy; next action is clear | No horizontal overflow; first Tab reaches “Skip to main content” |
| Profile | Baseline/current language remains distinct | Cards stack without clipped values |
| Practice library | Exactly five specific protocols | Three-column navigation wraps cleanly |
| Friendship | Recommendation and three actions are explicit | Setup explains eligible score behavior |
| Play | Non-instrumental boundary is visible | Setup says it is score-inactive |
| Emotional cues | Hypothesis/direct-clarification boundary is visible | Setup says it is score-inactive |
| Boundary | Coercion, retaliation, and safety exclusions are visible | Setup says it is score-inactive |
| Attention-presence | Accessibility and anti-surveillance boundary is visible | Setup says it is score-inactive |

For every protocol, confirm:

- the recommendation can be understood without internal property names;
- the user does not invent the intervention;
- all three actions are visible before starting;
- privacy and interpersonal boundaries are specific;
- the compact check-in exposes only protocol-relevant fields;
- completion and review state that completion does not establish mastery;
- no score-inactive protocol claims a profile change.

## Engineering findings and responses

| Finding | Closeout response |
|---|---|
| The small-screen header compressed seven navigation actions into an uneven row. | Mobile navigation now uses three equal columns with full-width targets. |
| Keyboard users had to traverse the complete header before reaching the page. | A visible-on-focus skip link targets the main landmark. |
| Browser failures did not leave a reviewable artifact. | CI now retains screenshots and traces under `playwright-results`. |
| Three independent green jobs did not yield one obvious pilot decision. | The aggregate Pilot readiness gate fails unless quality, browser, and Compose all pass. |
| Protocol and scoring drift required several separate commands to detect. | The read-only versioned readiness verifier checks the reviewed boundary in one operation. |

These are software-readiness findings. They are not clinical,
psychometric, accessibility-pilot, or longitudinal validation.

## Exit criteria

The private pilot gate is satisfied only when:

- **Pilot readiness gate** passes on the exact reviewed commit;
- the retained desktop/mobile artifact has been visually reviewed;
- the live one-service deployment passes `make compose-smoke`;
- backup and restore have been exercised for the deployment;
- no unresolved critical safety, privacy, authentication, data-loss,
  keyboard-blocking, or horizontal-overflow finding remains;
- the instance owner explicitly approves proceeding.

## Proposed next milestone: M5A

After this closeout is approved, M5A should add bounded private-pilot
operations and feedback capture:

- an operator guide and session checklist;
- optional structured usability feedback kept separate from developmental
  evidence;
- applicability, time-to-start, time-to-check-in, confusing-step, and
  accessibility/safety-friction fields;
- a privacy-minimized pilot export with an explicit schema version;
- tests proving feedback cannot alter assessment, evidence, score state,
  recommendation order, completion, orientations, or archetypes.

M5A should not activate another protocol for scoring, change posterior
mathematics, add protocols, add remote telemetry, or send participant data to
an external service. Any such expansion requires its own reviewed batch.
