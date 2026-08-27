# Protocol library

## Current M6F runtime and scoring boundary

The canonical library now contains one runtime protocol for each of the 383
competencies and 1,151 stable actions. All 383 protocols are available and
score active under the explicit M6F activation ledger. The five original
protocols keep their version-1 observation snapshots for historical replay;
the remaining 378 protocols use typed structured evidence.

Score activity means an eligible, replay-verified event may update the separate
current working lever state through the protocol's canonical parent competency
mapping. It does not modify the published assessment baseline and does not
establish mastery, identity, dignity, worth, clinical status, or broad transfer.
Unknown, withheld, adverse, contradictory, and inconclusive states retain their
explicit fail-closed or withholding behavior.

The M4, M6A, and M6D sections below document how the library evolved. Their
former activation ceilings are historical and are superseded by M6F.

## M4A boundary

M4A activates `PRACTICE-PLAY-01`, **Schedule Non-Instrumental Play**, as the
second executable protocol. It is a 10-day experiment anchored to canonical
competency `26.01`, Play for its own sake.

The user chooses one safe, accessible activity and follows three defined
actions:

1. reserve a specific 30-minute play window within three days;
2. engage without optimizing, publishing, measuring, or producing an output;
3. return once within seven days.

Completion requires all three actions attempted, at least two completed, at
least one record of non-instrumental engagement, and a final review.
Completion does not establish mastery.

## Reusable protocol configuration

`PracticeProtocol` now stores version-neutral configuration for:

- setup headings, help, and boundary acknowledgement;
- the compact check-in fields shown to the user;
- protocol-specific labels over stable observation fields;
- minimum completed actions and markers required for a meaningful attempt;
- explicit score activation.

Actions continue to carry stable IDs and validated
`practice-observation-v1` rules. The canonical importer validates the parent
competency, structured competency-to-lever weights, target-lever subset, and
every action rule before writing.

## Scoring boundary

Availability and scoring remain independent fields. At M4, friendship alone
was `score_active=true`; M6F supersedes that historical boundary and activates
all canonical runtime protocols through one machine-validated contract.

M4A deliberately reuses the existing v1 structured observation vocabulary
with protocol-specific user-facing labels. Adding fields to the v1 snapshot
would break exact replay of historical events. New observation semantics must
use a separately reviewed evidence algorithm version.

## M4B boundary

M4B activates `PRACTICE-EMOTIONAL-CUES-01`, **Practice Emotional Cue
Detection**, as a 10-day experiment anchored to canonical competency `16.03`,
Nonverbal communication.

The three fixed actions are:

1. notice one observable change without assigning a feeling or motive;
2. hold at least two tentative explanations, including one unrelated to the user;
3. ask a neutral clarification question and compare the response or later
   information with the initial impression within seven days.

Completion requires all three actions attempted, at least two completed, at
least one impression checked through direct clarification, and a final review.
The protocol explicitly warns against mind-reading, diagnosis, covert testing,
and universal interpretations of eye contact or body language. Culture,
disability, neurotype, stress, and habit are named sources of variation.

The stable parent maps canonically to L23, L24, and L05. The protocol targets
only L24 for recommendation. It was score-inactive at M4. The placeholder's
earlier L06 target is not inferred into the canonical parent mapping.

## M4C boundary

M4C activates `PRACTICE-BOUNDARY-01`, **State and Maintain One Boundary**, as
a 10-day experiment anchored to canonical competency `11.10`, Saying no and
ending responsibly.

The three fixed actions are:

1. define one low-stakes limit and a proportionate response the user controls;
2. state the boundary directly without threats, punishment, or a silent test;
3. follow through once or calmly restate the limit within seven days.

Completion requires all three actions attempted, at least two completed, both
a direct statement and a proportionate follow-through, and a final review.
The reusable completion rules retain `any` as the default marker behavior and
add an explicit `all` mode for this two-part criterion.

The setup distinguishes a boundary from control: another person does not have
to agree, and the intervention cannot depend on forcing compliance. It excludes
abuse, coercive control, stalking, discrimination, unsafe dependency, and
likely-retaliation contexts. Those situations call for safety planning and
appropriate trusted, professional, legal, medical, or organizational support,
not a guided confrontation.

Canonical parent `11.10` maps to L25, L36, L10, and L29. The protocol targets
only L25 for recommendation. It was score-inactive at M4. M4C does not bind the
generic practice to the higher-risk bodily-autonomy or harmful-relationship
competencies.

## M4D boundary

M4D activates `PRACTICE-PRESENCE-01`, **Complete an Attention-Presence
Experiment**, as a 10-day experiment anchored to canonical competency `08.02`,
Mindfulness and present attention.

The three fixed actions are:

1. run a 15-minute window under the user's usual safe conditions;
2. repeat the same activity after changing exactly one controlled condition;
3. repeat the more workable condition within seven days.

The comparison concerns noticing and returning attention, not output,
distraction counts, or perfect concentration. Completion requires all three
actions attempted, at least two completed, an actual condition comparison, a
repeat within seven days, and a final review.

Presence is not equated with stillness, silence, eye contact, or zero
distraction. Movement, fidgets, assistive technology, reminders, and necessary
alerts are valid. The protocol does not run during driving, equipment
operation, hazard supervision, or after disabling emergency, accessibility,
or caregiving alerts. It requires no surveillance or recording of another
person.

Canonical parent `08.02` maps to L08, L03, and L17. The protocol targets only
L08 for recommendation. It was score-inactive at M4.

All five original protocols were executable by M4. Availability alone still
does not authorize scoring; M6F provides the explicit all-383 activation ledger.

## Post-M4 freeze

`GG-PILOT-READINESS-1.0` originally treated these five protocols and fifteen
stable actions as the private-pilot inventory. Its implementation now preserves
those legacy contracts while also requiring the M6F 383/1,151/383 boundary. Run:

```bash
make pilot-check
```

The verifier is read-only and fails on drift. Expanding the library or score
activation requires a new reviewed contract version; it must not be smuggled
through a seed edit. See
`docs/pilot/PILOT_READINESS_CLOSEOUT.md`.

## M6A canonical source

M6A moves the exact five-protocol configuration from the importer into
manifest-listed, schema-validated packages under `data/practices/protocols/`.
The ORM and ordinary user experience are unchanged. Rich source, risk,
adaptation, reflection, and evidence-design metadata remains source-only.

The original activation ledger kept only friendship active. M6F replaces it
with exact all-catalog activation while retaining a compatibility hash over the
five legacy projections in the release manifest.

`GG-CURRICULUM-EXPANSION-READINESS-1.0` calls the unchanged old verifier,
checks the canonical packages and generated reports, and compares them with
the seeded database. See `docs/practice-content.md`.

## M6D-01 source-only drafts

The canonical source catalog now also contains four individually authored
drafts: Motivation-Independent Start (`08.06`), Decision Record and Update
(`09.12`), Deliberate Practice Loop (`10.02`), and Home Upkeep System (`13.02`).
They exercise behavioral experiment, artifact plan, skill rehearsal, and audit
redesign families. M6F makes all four available and score active using typed
structured evidence. Their safety boundaries exclude coercive productivity,
sensitive decision detail, dangerous or licensed practice, and hazardous or
landlord/tradesperson home work.
