from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from growth.models import (
    ArchetypeResult,
    AssessmentRun,
    Competency,
    CompetencyLeverLink,
    CurriculumVersion,
    Lever,
    LeverBaseline,
    OrientationResult,
    PracticeAction,
    PracticeProtocol,
)
from growth.services.canonical_import import (
    CanonicalDataError,
    _mapping_weights,
    load_and_validate_bundle,
    seed_canonical_data,
)


def test_canonical_bundle_has_expected_unique_stable_ids_and_valid_weights():
    bundle = load_and_validate_bundle()
    domains = bundle.curriculum["domains"]
    competency_ids = [
        competency["id"] for domain in domains for competency in domain["competencies"]
    ]
    family_ids = [family["id"] for family in bundle.model["lever_families"]]
    lever_ids = [lever["id"] for lever in bundle.model["developmental_levers"]]
    orientation_ids = [orientation["id"] for orientation in bundle.model["orientation_modes"]]
    archetype_ids = [archetype["id"] for archetype in bundle.model["archetypes"]]
    mapping_ids = [row["competency_id"] for row in bundle.mapping_rows]

    assert len(domains) == len({domain["id"] for domain in domains}) == 27
    assert len(competency_ids) == len(set(competency_ids)) == 383
    assert len(family_ids) == len(set(family_ids)) == 7
    assert len(lever_ids) == len(set(lever_ids)) == 37
    assert len(orientation_ids) == len(set(orientation_ids)) == 6
    assert len(archetype_ids) == len(set(archetype_ids)) == 15
    assert sum(len(archetype["lever_affinity"]) for archetype in bundle.model["archetypes"]) == 555
    assert set(mapping_ids) == set(competency_ids)
    assert all(
        sum(_mapping_weights(row).values(), Decimal("0")) == Decimal("1")
        for row in bundle.mapping_rows
    )


def test_mapping_validator_rejects_partial_and_malformed_slots():
    partial = {"competency_id": "X", "lever_1_id": "L01", "lever_1_weight": ""}
    with pytest.raises(CanonicalDataError, match="both ID and weight"):
        _mapping_weights(partial)

    invalid = {
        "competency_id": "X",
        "lever_1_id": "L01",
        "lever_1_weight": "not-a-number",
    }
    with pytest.raises(CanonicalDataError, match="invalid weight"):
        _mapping_weights(invalid)


@pytest.mark.django_db
def test_repeated_seed_is_idempotent_and_imports_pilot_profile(user):
    first = seed_canonical_data()
    counts_after_first = {
        "versions": CurriculumVersion.objects.count(),
        "levers": Lever.objects.count(),
        "competencies": Competency.objects.count(),
        "links": CompetencyLeverLink.objects.count(),
        "runs": AssessmentRun.objects.count(),
        "orientations": OrientationResult.objects.count(),
        "archetypes": ArchetypeResult.objects.count(),
        "baselines": LeverBaseline.objects.count(),
        "protocols": PracticeProtocol.objects.count(),
        "actions": PracticeAction.objects.count(),
    }
    second = seed_canonical_data()
    counts_after_second = {
        "versions": CurriculumVersion.objects.count(),
        "levers": Lever.objects.count(),
        "competencies": Competency.objects.count(),
        "links": CompetencyLeverLink.objects.count(),
        "runs": AssessmentRun.objects.count(),
        "orientations": OrientationResult.objects.count(),
        "archetypes": ArchetypeResult.objects.count(),
        "baselines": LeverBaseline.objects.count(),
        "protocols": PracticeProtocol.objects.count(),
        "actions": PracticeAction.objects.count(),
    }

    assert first == second
    assert (
        counts_after_first
        == counts_after_second
        == {
            "versions": 1,
            "levers": 37,
            "competencies": 383,
            "links": 1403,
            "runs": 1,
            "orientations": 6,
            "archetypes": 3,
            "baselines": 37,
            "protocols": 5,
            "actions": 3,
        }
    )
    assert AssessmentRun.objects.get().assessment_version == "1.1"
    assert ArchetypeResult.objects.get(stable_id="A03").name == "The Systems Steward"
    assert LeverBaseline.objects.get(lever_id="L26").need_rank == 1
    assert (
        PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01").mastery_disclaimer
        == "Completing this practice does not establish mastery."
    )
    assert (
        PracticeProtocol.objects.filter(availability=PracticeProtocol.Availability.INACTIVE).count()
        == 4
    )


@pytest.mark.django_db
def test_seed_without_user_imports_global_data_and_defers_pilot():
    assert not get_user_model().objects.exists()
    summary = seed_canonical_data()
    assert summary.levers == 37
    assert summary.competencies == 383
    assert summary.pilot_assessment_runs == 0
    assert not AssessmentRun.objects.exists()
