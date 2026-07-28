# Canonical data import

## Sources

`seed_canonical` reads:

1. `data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml`
2. `data/model/grounded_growth_model_v1.json`
3. `data/model/competency_lever_mapping_v1.csv`
4. `data/practices/release_manifest.yaml` and every package, registry, and
   schema it explicitly lists
5. `data/notion/initial_mvp/01_lever_baselines_import.csv`
6. `data/notion/initial_mvp/03_orientation_profile_import.csv`

The first four define global curriculum/model and practice rows. The last two
initialize Pilot 002 for the first application user. The three Pilot 002 archetypes come
from the stable IDs and exact fit indexes published in
`data/notion/initial_mvp/04_starting_profile_page.md`.

The importer never uses `legacy/` and never parses the human-readable Notion
`Lever Mapping` field.

## Independently verified counts

| Dataset | Count |
|---|---:|
| Curriculum domains | 27 |
| Competencies | 383 |
| Lever families | 7 |
| Developmental levers | 37 |
| Orientations | 6 |
| Archetypes in the model | 15 |
| Competency-to-lever links | 1,403 |
| Archetype-to-lever affinities | 555 |
| Pilot 002 lever baselines | 37 |
| Pilot 002 orientation results | 6 |
| Pilot 002 published archetype results | 3 |
| Seeded practice protocols | 5 |
| Seeded practice actions | 15 |
| Canonical practice packages | 5 |
| Explicit unauthored competency rows | 378 |

## Validation before writes

The command opens one transaction and fails before model writes when it finds:

- blank or duplicate domain, competency, lever, or mapping IDs;
- declared curriculum counts that do not match actual rows;
- missing or extra competency mappings;
- unknown lever IDs;
- a mapping slot with only an ID or only a weight;
- nonnumeric, nonpositive, or greater-than-one weights;
- competency weights that differ from 1.0 by more than `0.000001`;
- disagreement between the structured mapping CSV and canonical model JSON;
- an unknown practice-content, registry, activation, or release version;
- a missing, duplicate, unlisted, traversing, or misplaced manifest path;
- a repository-source locator that is missing, escaping, or differs from its
  recorded SHA-256;
- a protocol or registry field outside its offline JSON Schema;
- duplicate protocol/action/source/risk/policy/family/activation stable IDs or
  broken cross-references;
- a practice package whose domain differs from its canonical parent or whose
  recommendation targets fall outside the parent's structured mapping;
- a package/content hash mismatch or a runtime projection that differs from
  the reviewed five-protocol fingerprint;
- an activation-ledger mismatch or score activation beyond friendship;
- a release candidate with unresolved global or protocol-scoped research,
  specialist, accessibility, originality, source, or UI/test gates;
- a scoreable protocol whose stable parent competency is missing, whose
  recommendation targets are not a non-empty subset of its mapping, or whose
  structured weights are malformed;
- a practice action with a missing schema version, noncanonical action ID,
  due window beyond its protocol duration, unknown/uncollectable observation
  field without the one frozen exception, duplicate marker, or overlapping
  primary/supporting evidence marker;
- an invalid completion minimum, completion marker outside the reviewed
  observation vocabulary, unsupported completion-marker mode, or score
  activation beyond the reviewed friendship protocol.

No malformed value is silently normalized.

## Run and inspect

In Docker:

```bash
docker compose exec app python manage.py seed_canonical
```

For local development:

```bash
make migrate
make seed
make pilot-check
make practice-report-check
make curriculum-check
```

A successful command reports the imported counts. Repeated runs update
canonical rows by stable ID, remove stale weighted links, and do not duplicate
entities, assessment runs, baselines, protocols, or actions.

Every executable action receives validated `practice-observation-v1` evidence
rules keyed by stable action IDs. Seeding links friendship to `17.03`, play to
`26.01`, emotional cue detection to `16.03`, and boundary practice to `11.10`,
and attention-presence practice to `08.02`, then validates each
recommendation-target subset against canonical structured weights. Completion
rules may require any configured marker or all configured markers; every
marker must remain in the reviewed observation vocabulary. Seeding does not
create evidence events.
`backfill_evidence_events` runs afterward and creates events only for submitted
check-ins that do not already have one. `rebuild_score_state` then initializes
or reconciles current state from those events; canonical seeding itself does
not score a check-in.

## Versioning

`CurriculumVersion` records:

- curriculum version;
- model version;
- assessment version;
- SHA-256 over the curriculum, model, and mapping source bytes;
- import timestamp.

Assessment runs and practice sprints retain their curriculum-version
reference. M2A records `GG-EVIDENCE-1.0` separately on each immutable event.
M2B verifies and exports those stored versions without altering canonical data
or authorizing dynamic scoring. M3A records the stable parent competency on
the protocol and established `GG-SCORING-SHADOW-1.0`. M3B retains that exact
math version and separately records `GG-SCORE-STATE-1.0` and
`GG-NEED-RANKING-1.0`.
The post-M4 `GG-PILOT-READINESS-1.0` verifier then checks the exact reviewed
source/database counts, protocol/action/link inventory, Pilot 002 shape, and
replay boundaries without writing or repairing canonical data.

M6A keeps that hash and verifier unchanged. The practice release stores a
separate deterministic content hash because editorial protocol metadata is
not an assessment curriculum version. The additive
`GG-CURRICULUM-EXPANSION-READINESS-1.0` contract invokes the old verifier,
checks the manifest/packages/reports, and compares the exact canonical
projection with the seeded database.

The five packages are `projected_legacy`. Rich research, safety, adaptation,
reflection, and evidence-design metadata remains source-only in M6A; it does
not expand the ORM or execute a new evidence algorithm.

## Pilot 002 boundary

Pilot 002 is a demonstration seed, not a reconstructed assessment. Its
canonical files do not provide original answers, clarifier answers, a GGA11
code, or the complete 15-archetype vector. M1 stores those unavailable fields
as empty and imports only the six orientations, 37 baselines, response-quality
summary, timing summary, and three published archetypes. It does not invent
missing source data.

For M3A, the seed reconstructs Pilot 002 alpha/beta mass from the published
rounded raw and calibrated values only when the canonical equal-prior
equations identify one solution. It records
`published_reconstruction` as the source. Neutral `0.5000`/`0.5000` pairs are
ambiguous and remain null; the importer does not infer mass from confidence.
All four levers required by competency `17.03` are identifiable. M3B creates
37 separate current states: 33 evidence-active and L06, L15, L32, and L37
baseline-only. Taking or importing v1.1 is the upgrade path before a future
practice can score one of those four.

The seed remains idempotent after a user takes or imports another assessment.
It reconciles the stable Pilot 002 row but does not overwrite or remove
user-created immutable assessment runs, practice sprints, check-ins, or
reviews.

## Existing M1 check-ins

After upgrading, run:

```bash
python manage.py backfill_evidence_events --dry-run
python manage.py backfill_evidence_events
python manage.py rebuild_score_state
python manage.py rebuild_score_state --verify-only
```

The command leaves submitted check-ins unchanged. Missing M1 support/context
metadata uses conservative factors, and absent contradiction remains unknown
rather than supportive. Repeated runs verify existing event snapshots and
create no duplicates. Score-state rebuild processes each event at most once,
retains immutable before/after snapshots, and appends a repair snapshot only
when deterministic replay finds current-state drift.
