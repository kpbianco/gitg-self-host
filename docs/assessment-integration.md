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

## M1 implementation

The authenticated `/assessment/` page renders the canonical specification
through Django templates and loads:

- the exact canonical `assessment_scoring_v1_1.js` from an authenticated local
  Django route;
- a small local controller for question navigation, timing, autosave,
  clarifiers, result presentation, import, and persistence;
- no CDN, external CSS/JavaScript, frontend framework, or runtime Node server.

The page requires all 50 core questions, records the full interval from
question display until Next/Back, and offers the engine's targeted capability
and orientation clarifiers. It displays a concise result while retaining the
complete output.

The CSRF-protected persistence endpoint validates:

- submission UUID, source, and assessment version;
- all 50 canonical core IDs and response ranges;
- optional clarifier IDs and N/A applicability;
- complete core timing for an in-app run;
- exact agreement between submitted answers and the original share code;
- all 6 orientation, 15 archetype, and 37 lever outputs;
- canonical alpha/beta/evidence-mass agreement for every assessed lever;
- the complete 37-lever need ranking and finite output ranges.

It then atomically writes an immutable `AssessmentRun` with:

- assessment/curriculum versions and source;
- answers and clarifier answers;
- timing and response-quality result;
- orientation and archetype outputs;
- raw lever scores, calibrated estimates, and confidence;
- exact six-decimal alpha/beta baseline mass for later replayable projections;
- original share code and creation timestamp.

Related orientation, archetype, and lever-baseline rows support efficient
profile rendering. Saving an existing `AssessmentRun` through the model raises
a validation error. A repeated submission UUID returns the original run
without duplicating it.

The import panel decodes GGA11 or supported GGA1 locally, scores the decoded
answers through the same canonical v1.1 engine, preserves the original code,
and uses the same validated persistence path. The displayed portable result is
always a current GGA11 code.

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

pytest also checks SHA-256 hashes for the engine, spec, input, and output. The
integrated persistence test passes that same golden result through Django and
verifies the exact 6/15/37 related rows and representative raw, calibrated,
confidence, and need values. Playwright completes all 50 questions and imports
both GGA11 and GGA1 in a real browser.

## Integration defects corrected

The standalone HTML exposed capability clarifiers but did not expose the
canonical spec's optional orientation clarifiers. The integrated controller
uses both suggestion lists—up to eight capability and two orientation
clarifiers—without changing wording or scoring.

The canonical scorer can return null raw/calibrated/need values when every
relevant response is genuinely N/A. M1 therefore permits null in those
baseline fields instead of coercing an unsupported score.

## Assessment-baseline boundary

The canonical scorer also contains future evidence-update helper functions.
M1 and M2 do not call or persist their task-update output. M3A implemented the
posterior reference and a versioned, assessment-anchored confidence correction
in a pure Python Decimal package. M3B activates that accepted server-side
contract in separate `LeverState` rows. It never rewrites assessment
baselines, raw self-report, orientations, or archetypes. Completion and final
review create no score event.

Browser scoring is a stated M1 trust boundary. Django verifies shape, IDs,
ranges, version, share-code/answer agreement, and internal consistency of
alpha/beta/evidence mass. It does not maintain a second initial-assessment
scorer. The M3A server-side code starts from the browser scorer's persisted
mass and has a separate version, contract, and golden suite. M3B creates 37
current states and an initialization snapshot when a new assessment is saved;
an idempotent repeat submission creates neither a new run nor a new snapshot.
