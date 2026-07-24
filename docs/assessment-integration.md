# Assessment v1.1 integration

## Canonical boundary

Assessment v1.1 under
`data/assessment/v1.1_bundle/grounded_growth_assessment_v1_1/` is canonical.
Its substantive behavior must remain unchanged:

- 50 mandatory core questions;
- optional capability and orientation clarifiers;
- full-question timing;
- response-quality handling;
- raw self-report, calibrated estimate, and evidence confidence;
- six orientation and 15 archetype outputs;
- 37 lever outputs;
- GGA11 generation and supported GGA1 decoding.

The browser-side `assessment_scoring_v1_1.js` remains the M1 reference
implementation.

## M1A implementation

M1A provides an immutable `AssessmentRun` schema for:

- assessment/curriculum versions and source;
- answers and clarifier answers;
- timing and response-quality result;
- orientation and archetype outputs;
- raw lever scores, calibrated estimates, and confidence;
- original share code and creation timestamp.

Related orientation, archetype, and lever-baseline rows support efficient
profile rendering. Saving an existing `AssessmentRun` through the model raises
a validation error.

M1A does not yet expose assessment-taking or share-code import.

## Golden fixture

The pre-integration input is:

```text
pilot_001_responses_v1_compatible.json
```

The complete expected output is:

```text
pilot_001_rescore_v1_1.json
```

Run:

```bash
node scripts/verify_assessment_golden.js
```

The verifier removes only the nondeterministic `generated_at` field and the
fixture's explanatory `note`, then deep-compares every substantive output. It
also:

- generates a GGA11 code and round-trips all 58 core/clarifier answers;
- decodes the canonical legacy GGA1 code;
- confirms 37 lever and 15 archetype outputs.

pytest also checks SHA-256 hashes for the engine, spec, input, and output.

## M1B integration plan

1. Extract the existing standalone markup into Django templates without
   changing question wording or scoring constants.
2. Copy the canonical scorer into a locally served static asset; do not load
   it from a CDN.
3. Post the complete answers, clarifiers, timings, quality result, outputs,
   and original GGA11 code to a CSRF-protected Django endpoint.
4. Validate payload shape, IDs, version, and output completeness server-side
   before one atomic immutable insert.
5. Add a separate GGA11 import form using the same canonical decoder and
   persistence path.
6. Retain GGA1 decoder coverage.
7. Run the same golden fixture through both the standalone reference and
   integrated page.
8. Add Playwright coverage for completion and share-code import.

## Static-score boundary

The canonical scorer also contains future evidence-update helper functions.
The Django application does not import, call, or persist their output in M1.
Assessment baselines, mastery, confidence, need, orientations, and archetypes
remain unchanged after practices and reviews.
