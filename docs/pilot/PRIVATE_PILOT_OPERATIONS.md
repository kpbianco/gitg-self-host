# Private pilot operations

## Scope

This guide runs one bounded private-pilot session against a self-hosted
Grounded Growth instance. It evaluates comprehension, activation, timing, and
usability friction. It does not evaluate participant worth, diagnose a
condition, validate the assessment psychometrically, or authorize a new
scoring rule.

Do not observe or record a participant's real-world private interaction. The
pilot covers the application flow and, when appropriate, a participant's own
later self-report.

## Before the session

- [ ] Use the exact commit approved for the pilot.
- [ ] Run `make compose-smoke` on a Docker-capable host.
- [ ] Confirm the GitHub **Pilot readiness gate** passed on that commit.
- [ ] Review the retained desktop/mobile walkthrough artifact.
- [ ] Confirm `make m6c-pilot-check` passed and review the synthetic Personal
      OS/context artifact for private-value leakage and partial-cohort wording.
- [ ] Run `make backup` and record the backup filename.
- [ ] Confirm `/health/` and an authenticated login through the configured LAN
      address.
- [ ] Change the bootstrap password and remove
      `APP_BOOTSTRAP_PASSWORD` from `.env`.
- [ ] Keep the instance on the intended private network; do not expose direct
      HTTP to the public internet.
- [ ] Explain what will be collected and obtain the participant's voluntary
      agreement before continuing.

Use this concise participant framing:

> Grounded Growth presents a provisional assessment and bounded practices. It
> does not measure human worth or establish mastery. Product feedback is
> optional, stays on this self-hosted instance, and does not change your
> assessment, evidence, scores, recommendations, or practice completion. You
> may skip a question or stop the session at any time.

Before opening Personal OS, also explain:

> Personal OS and context answers are optional private local data included in
> normal database backups. Use minimal detail. Authored Personal OS text is not
> analyzed or used in recommendations; only explicit structured context may
> reorder the practices you have reviewed. This version has no dedicated
> Personal OS/context export, purge, automatic retention, or urgent-support
> monitoring.

## Session path

The operator may note elapsed time outside the application for facilitation,
but must not install analytics or enter an exact timestamp into participant
feedback. The participant selects only a rough time band if they choose to
report it.

1. **Login and orientation — about 3 minutes**
   - Ask the participant to sign in without coaching unless blocked.
   - Confirm they can identify the current profile, current practice, and next
     action.
2. **Profile comprehension — about 5 minutes**
   - Ask what raw self-report, current estimate, and confidence appear to mean.
   - Confirm the participant does not interpret archetypes as diagnoses or
     scores as worth.
3. **Optional Personal OS and context review — about 5 minutes**
   - Confirm the staged page can be understood without completing every field.
   - Encourage minimal detail and permit unknown, N/A, or defer without
     pressure; do not interpret or copy the participant's authored text.
   - Review at most one active practice at a time. Do not preselect or suggest a
     0–4 factor, and do not treat an unreviewed practice as unfavorable.
   - Confirm any ranking is described as among explicitly reviewed practices,
     and that an N/A/defer alternative is distinct or explicitly unavailable.
4. **Recommendation and applicability — about 5 minutes**
   - Ask why the first practice appears to have been selected.
   - Let the participant decide whether it currently fits; do not pressure
     them to make a protocol applicable.
5. **Guided setup — target under 5 minutes**
   - Let the participant move through setup without inventing a new
     intervention.
   - Stop if the privacy, relationship, accessibility, or safety boundary does
     not fit.
6. **Compact check-in — target under 2 minutes**
   - Use a real check-in only after an actual action. For an interface-only
     session, inspect the blank form without submitting fabricated evidence.
   - Confirm the page shows only prompts relevant to the selected action.
   - Before an action occurs, save a draft; the application must refuse a
     submitted evidence record without an attempt.
   - Confirm draft and submitted evidence are understood as different states.
7. **Optional product feedback — about 3 minutes**
   - Open **Account → Open feedback form**.
   - Choose one journey stage per record and confirm irrelevant practice or
     timing questions are not shown.
   - The participant may answer any useful categories and omit the rest.
   - Do not ask the participant to include names, health details, relationship
     details, or other sensitive free text.

## Observation rules

The operator may ask neutral prompts such as:

- “What do you expect this button to do?”
- “What makes this practice feel applicable or not applicable?”
- “Which wording would you need to reread?”
- “Could you complete this with your current device or access needs?”
- “Did any instruction feel unsafe, coercive, or poorly bounded?”

Do not:

- explain the intended answer before observing the participant's
  interpretation;
- turn confusion into a developmental deficit;
- infer a score, diagnosis, personality trait, or motivation from feedback;
- copy private notes, assessment answers, share codes, person/context labels,
  or exact event times into an external tracker;
- record audio, video, browser activity, or keystrokes through this product;
- submit a check-in for an action that did not occur.

## Safety and accessibility response

If a participant reports safety friction, pause the guided flow. Do not
encourage completion for the sake of the pilot. A potentially unsafe
relationship, coercion, retaliation, crisis, medical issue, legal issue, or
workplace issue belongs with appropriate trusted, professional, medical,
legal, organizational, or emergency support—not this form.

Accessibility friction is a product finding, not evidence of inability.
Preserve assistive technology, movement, reminders, and safety/access alerts.
Record only the minimum product detail required to reproduce the interface
barrier.

## After the session

- [ ] Confirm any submitted product feedback appears only on the feedback
      page—not in Evidence.
- [ ] Download the minimized JSON from the feedback page.
- [ ] Open the file and confirm it contains no name, IDs, exact timestamp,
      comment text, assessment data, evidence value, or score.
- [ ] Do not place a participant name in the export filename.
- [ ] Store the export as sensitive private-pilot data with limited access.
- [ ] Record product defects as repository issues without copying private
      participant content.
- [ ] Apply the agreed retention period. If feedback must be removed, preview
      `purge_pilot_feedback --username <username>` before using `--confirm`,
      and handle any backups under the same agreement.
- [ ] Run `docker compose exec app python manage.py
      verify_pilot_readiness`.
- [ ] Run `docker compose exec app python manage.py
      verify_m6c_pilot_readiness` and confirm its output contains no authored
      Personal OS/context value.
- [ ] Back up after the session if the instance state must be retained.

## Stop criteria

Stop or postpone the pilot when:

- authentication, persistence, backup/restore, or the health check fails;
- the **Pilot readiness gate** is not green for the deployed commit;
- private data appears in a minimized export;
- Personal OS authored text appears in recommendation copy, logs, messages,
  URLs, a non-Personal-OS retained artifact, or readiness output;
- a recommendation silently includes an unreviewed practice, treats unknown,
  N/A, or defer as zero, or returns the source as its own alternative;
- feedback changes evidence, score state, recommendations, or completion;
- a critical keyboard, mobile, accessibility, privacy, or safety issue blocks
  the participant;
- the participant withdraws or no longer wants to continue.

See [the feedback contract](../pilot-feedback.md) and
[the post-M4 readiness closeout](PILOT_READINESS_CLOSEOUT.md).
