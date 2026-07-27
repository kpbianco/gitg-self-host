# Protocol library

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

Availability and scoring are independent. The friendship protocol is
`score_active=true`; the play protocol is `score_active=false`. Play
submissions create immutable evidence events but no score snapshot and no
change to current lever state, confidence, need, or recommendation order.

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
only L24 for recommendation and remains score-inactive. The placeholder's
earlier L06 target is not inferred into the canonical parent mapping.

The remaining two placeholders stay inactive. No protocol becomes
score-active merely because it becomes executable.
