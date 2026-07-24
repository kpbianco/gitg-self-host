# Assessment v1.1 golden fixture

The golden test deliberately references the canonical, pre-integration files
instead of copying them:

- `pilot_001_responses_v1_compatible.json` is the known input.
- `pilot_001_rescore_v1_1.json` is the expected complete output.
- `assessment_scoring_v1_1.js` is the browser-side reference engine.
- `assessment_spec_v1_1.json` is the canonical assessment definition.

`scripts/verify_assessment_golden.js` removes only nondeterministic metadata
(`generated_at`) and the fixture annotation (`note`), then deep-compares every
substantive output. It also verifies GGA11 round-trip encoding and the existing
GGA1 compatibility code.

The hashes in `manifest.json` make fixture drift explicit during pytest. The
Django persistence test uses this same input and complete output, while
Playwright verifies the mounted 50-question and import paths.
