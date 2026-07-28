# Shadow scoring fixtures

`shadow_v1.json` is a synthetic, privacy-free golden case for
`GG-SCORING-SHADOW-1.0`. It covers supportive, mixed, contradictory,
inconclusive, and legacy direction-unknown evidence against the reviewed
`17.03` task-to-lever weights.

The fixture locks software behavior for review. It is not psychometric
validation and does not authorize persistence or recommendation changes.

`competency_shadow_v1.json` locks the separate, evidence-only
`GG-COMPETENCY-EVIDENCE-SHADOW-1.0` and one-way
`GG-COMPETENCY-LEVER-SHADOW-1.0` contracts. It covers explicit withholding,
reversal, an unknown zero-evidence state, full parent mapping, and assessment
epoch isolation without inventing a competency baseline.
