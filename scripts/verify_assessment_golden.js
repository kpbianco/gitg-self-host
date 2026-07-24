"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const bundle = path.join(
  root,
  "data",
  "assessment",
  "v1.1_bundle",
  "grounded_growth_assessment_v1_1",
);
const engine = require(path.join(bundle, "assessment_scoring_v1_1.js"));
const spec = JSON.parse(fs.readFileSync(path.join(bundle, "assessment_spec_v1_1.json"), "utf8"));
const model = JSON.parse(fs.readFileSync(path.join(bundle, "grounded_growth_model_v1.json"), "utf8"));
const input = JSON.parse(
  fs.readFileSync(path.join(bundle, "pilot_001_responses_v1_compatible.json"), "utf8"),
);
const expected = JSON.parse(
  fs.readFileSync(path.join(bundle, "pilot_001_rescore_v1_1.json"), "utf8"),
);

const actual = engine.scoreAssessment(spec, model, input);
delete actual.generated_at;
delete expected.generated_at;
delete expected.note;
assert.deepStrictEqual(actual, expected, "Pilot 001 scoring output changed");

const shareCode = engine.encodeShareCode(spec, input);
assert.match(shareCode, /^GGA11\./);
const roundTrip = engine.decodeShareCode(spec, shareCode);
assert.deepStrictEqual(roundTrip.responses, input.responses, "GGA11 response round trip changed");

const legacyCode =
  "GGA1.eyJ2IjoiMS4wIiwiciI6IjU1MzQ0MzQyNDI0NDQ0MzMyMzQzMjQzNTQ0NDQzNDU0NDQzMjIyMzQ0NDMzMzE0NDM0IiwiZSI6eyJDX0wzNCI6MiwiQ19MMzUiOjMsIkNfTDA1Ijo0LCJDX0wwOSI6MywiQ19MMTkiOjQsIkNfTDI2IjoyLCJDX0wwOCI6MywiQ19MMTciOjR9LCJ0Ijo0MC43ODc5OTk5OTk5OTk5OH0=";
const legacy = engine.decodeShareCode(spec, legacyCode);
assert.ok(Object.keys(legacy.responses).length >= 50, "GGA1 compatibility changed");

process.stdout.write(
  `${JSON.stringify({
    assessment_version: actual.assessment_version,
    core_answers: Object.keys(input.responses).filter((id) => id.startsWith("Q")).length,
    lever_outputs: Object.keys(actual.levers).length,
    archetype_outputs: actual.archetypes.length,
    share_prefix: shareCode.slice(0, 6),
    legacy_answers: Object.keys(legacy.responses).length,
  })}\n`,
);
