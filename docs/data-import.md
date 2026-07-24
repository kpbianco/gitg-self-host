# Canonical data import

## Sources

`seed_canonical` reads:

1. `data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml`
2. `data/model/grounded_growth_model_v1.json`
3. `data/model/competency_lever_mapping_v1.csv`
4. `data/notion/initial_mvp/01_lever_baselines_import.csv`
5. `data/notion/initial_mvp/03_orientation_profile_import.csv`

The first three define global curriculum/model rows. The last two initialize
Pilot 002 for the first application user. The three Pilot 002 archetypes come
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
- a practice action with a missing schema version, unknown observation field,
  duplicate marker, or overlapping primary/supporting evidence marker.

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
```

A successful command reports the imported counts. Repeated runs update
canonical rows by stable ID, remove stale weighted links, and do not duplicate
entities, assessment runs, baselines, protocols, or actions.

The active friendship actions also receive validated
`practice-observation-v1` evidence rules keyed by stable action IDs. Seeding
does not create evidence events. `backfill_evidence_events` runs afterward and
creates events only for submitted check-ins that do not already have one.

## Versioning

`CurriculumVersion` records:

- curriculum version;
- model version;
- assessment version;
- SHA-256 over the curriculum, model, and mapping source bytes;
- import timestamp.

Assessment runs and practice sprints retain their curriculum-version
reference. M2A records `GG-EVIDENCE-1.0` separately on each immutable event.
This does not authorize dynamic scoring.

## Pilot 002 boundary

Pilot 002 is a demonstration seed, not a reconstructed assessment. Its
canonical files do not provide original answers, clarifier answers, a GGA11
code, or the complete 15-archetype vector. M1 stores those unavailable fields
as empty and imports only the six orientations, 37 baselines, response-quality
summary, timing summary, and three published archetypes. It does not invent
missing source data.

The seed remains idempotent after a user takes or imports another assessment.
It reconciles the stable Pilot 002 row but does not overwrite or remove
user-created immutable assessment runs, practice sprints, check-ins, or
reviews.

## Existing M1 check-ins

After upgrading, run:

```bash
python manage.py backfill_evidence_events --dry-run
python manage.py backfill_evidence_events
```

The command leaves submitted check-ins unchanged. Missing M1 support/context
metadata uses conservative factors, and absent contradiction remains unknown
rather than supportive. Repeated runs verify existing event snapshots and
create no duplicates.
