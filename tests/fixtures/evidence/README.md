# Evidence calibration fixtures

`calibration_v1.json` contains synthetic, privacy-free cases for the immutable
`GG-EVIDENCE-1.0` contract. The cases cover supportive, inconclusive, mixed,
contradictory, and conservative legacy-unknown readings.

`typed_v1.json` separately locks `GG-TYPED-EVIDENCE-1.0` measurement,
provenance, neutral-state, contradiction, adversity, rule-hash, and replay
behavior. It neither rewrites v1 evidence nor authorizes typed persistence or
production scoring.

These are golden software fixtures, not psychometric validation data and not
examples copied from a person. Any future algorithm version must add a new
fixture version rather than rewriting the expected outputs in place.
