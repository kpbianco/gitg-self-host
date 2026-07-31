# Current state

Last audited: 2026-07-29
Audited default branch: `main@c551d5b14bb6812b3fddaeb09a9f3031b2ef2704`

## Completed implementation

- M1A/B through M5A/B are merged.
- M6A canonical practice-content foundation is merged.
- M6B typed evidence, evidence-only competency shadow, one-way lever shadow,
  production eligibility, deterministic reports, and additive readiness are
  merged as software.
- Current canonical practice coverage remains five packages and fifteen actions
  across 383 competencies; 378 competencies are explicitly uncovered.
- Friendship remains the only production score-active protocol.

## Active gate

M6B is not accepted for mass authoring. `ER-M6A-003` is pending and
`RG-M6A-002` remains open. Required measurement, accessibility, and privacy/
safety review plus explicit owner acceptance must be recorded before M6C, Phase
B, or full authoring proceeds through the autopilot.

Run the local gate check:

```bash
./scripts/ensure-agent-env.py
.venv/bin/python scripts/check-m6b-governance-gate.py
```

## Planned sequence after the gate

1. M6C context factors and concise Personal OS.
2. Approximately 10–12 representative vertical-slice protocols.
3. Stable report-derived domain cohorts of approximately 8–15 competencies per
   human-reviewed target PR.
4. Whole-library scoring dispositions and shadow calibration.
5. Separately approved controlled activation cohorts.
6. Full integration, operations hardening, and diverse multi-cycle validation.

## Automation boundary

The target autopilot creates and repairs draft PRs but never merges Grounded
Growth target PRs. Control-plane batch-contract PRs may auto-merge after schema
and CI pass. Generated content, source research, fixtures, and CI do not replace
specialist or participant validation.
