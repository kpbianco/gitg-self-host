# Private Pilot 001 Findings

## Scope and limits

This record summarizes one owner-operated session on the reviewed M5A
self-hosted build. The session exercised the deployed application over a local
network and produced one privacy-minimized pilot-feedback export plus one
privacy-minimized evidence export.

This is a usability and input-integrity observation, not psychometric,
clinical, accessibility, or longitudinal validation. The submitted check-ins
are not treated here as proof of developmental change. One session cannot
establish a general participant pattern.

## Verified environment

- Reviewed source: M5A merge commit `3a2bece`.
- Deployment: one-service Docker Compose on a private local network.
- `GG-PILOT-READINESS-1.0`: passed against the running instance.
- Canonical inventory: 27 domains, 383 competencies, 37 levers, 15
  archetypes, 555 archetype affinities, 1,403 weighted links, five active
  protocols, and fifteen actions.
- Score activation: friendship only.
- Replay state: seven evidence events across two score-state runs.
- Consistent online SQLite backup: created before findings closeout.

No username, address, private context, exact time, free text, assessment
answer, share code, record ID, or score value is retained in this document.
The exports themselves remain sensitive private-pilot data and are not
committed.

## Participant-selected feedback

The single optional feedback record reported:

- the recommendation was applicable;
- setup took under two minutes;
- the check-in took under one minute;
- no confusing step;
- no accessibility friction;
- no safety friction.

No optional comment was included. These positive categorical responses are one
participant report, not a general usability conclusion.

## Observed form-coherence findings

### Finding 1 — Feedback questions were not scoped to the selected stage

The record selected the assessment journey stage while also attaching a
specific practice and answering setup/check-in timing questions. The M5A form
displayed every optional category regardless of the selected stage, so it
allowed a structurally ambiguous record even though the export itself remained
privacy-minimized and developmentally inert.

Response:

- progressively show practice and timing questions only for relevant journey
  stages;
- reject out-of-scope combinations server-side with a participant-facing
  explanation;
- retain and continue exporting the existing append-only M5A record unchanged.

### Finding 2 — Check-ins exposed observations from other actions

The evidence export contained positive observation fields that were not part
of the selected action's snapshotted primary or supporting markers. The
check-in page displayed the protocol-wide field union for every action, which
made unrelated choices easy to submit.

Response:

- derive the visible observation prompts from the selected action's reviewed
  `evidence_rules`;
- preselect the next required action when entering from the active-practice
  page;
- reject truthy markers that belong to another action at both form and service
  boundaries;
- preserve every existing immutable check-in and `GG-EVIDENCE-1.0` event.

### Finding 3 — A no-attempt check-in could become submitted evidence

One submitted event recorded `action_attempted=false` while also carrying a
supportive direction and positive observations. The operator guide already
said not to submit a check-in before a real action, but the application did not
enforce that instruction. For the score-active friendship protocol, that
combination could enter the reviewed scoring path with nonzero protocol
performance.

Response:

- require `action_attempted=true` for a new submitted check-in;
- retain draft saving for preparation before an action occurs;
- leave the evidence and scoring algorithms unchanged so historical replay
  remains exact;
- do not rewrite, delete, reinterpret, or silently normalize existing events.

## Participant-data lifecycle decision

Pilot feedback remains append-only during ordinary application use and is
never deleted automatically. Before a session, the instance owner must state
the intended retention period and whether de-identified findings will be kept.

If a participant withdraws or the agreed retention period ends, the instance
owner may preview and then explicitly delete only that local user's optional
pilot-feedback records with `purge_pilot_feedback`. This operation must not
touch assessment, evidence, score, practice, orientation, archetype, or review
state. Existing backups may still contain the deleted rows and must be handled
under the same retention agreement.

## M5B boundary

M5B addresses only these observed form-coherence and participant-data
lifecycle issues. It adds no telemetry, automatic timing, assessment change,
protocol, evidence algorithm, scoring algorithm, recommendation input, score
activation, or developmental inference.
