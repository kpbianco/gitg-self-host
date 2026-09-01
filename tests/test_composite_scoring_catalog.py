import json
from decimal import Decimal

from django.conf import settings

from growth.domain.composite_scoring import canonical_hash


def _report():
    return json.loads(
        (
            settings.BASE_DIR / "reports" / "practice-content" / "composite_scoring_catalog_v1.json"
        ).read_text()
    )


def test_composite_catalog_assigns_every_entity_one_score_disposition():
    report = _report()

    assert report["counts"] == {
        "actions": 1151,
        "competencies": 383,
        "domains": 27,
        "families": 7,
        "levers": 37,
        "practices": 383,
        "relationship_allocations": 1403,
    }
    assert len(report["competencies"]) == 383
    assert len(report["lever_coverage"]) == 37
    assert len(report["family_coverage"]) == 7
    assert len(report["domain_coverage"]) == 27
    assert report["disposition_summary"] == {
        "assessment_initializes_priority_only": 383,
        "actions_with_equal_completion_units": 1151,
        "actions_with_pre_closeout_score_effect": 0,
        "check_ins_without_score_effect": 383,
        "human_closeout_scored_practices": 383,
        "mastery_claims": 0,
        "maximum_not_sum_repetition_rule": 383,
        "missing_score_dispositions": 0,
    }
    assert report["governance"] == {
        "m6b_accepted": False,
        "research_gap_id": "RG-M6A-002",
        "research_gap_status": "open",
        "specialist_review_complete": False,
        "specialist_review_id": "ER-M6A-003",
        "specialist_review_status": "pending",
    }
    assert len({row["competency_id"] for row in report["competencies"]}) == 383
    assert len({row["protocol_id"] for row in report["competencies"]}) == 383
    assert (
        len({action_id for row in report["competencies"] for action_id in row["action_ids"]})
        == 1151
    )
    action_dispositions = [
        action for row in report["competencies"] for action in row["action_dispositions"]
    ]
    assert len(action_dispositions) == 1151
    assert len({action["action_id"] for action in action_dispositions}) == 1151
    assert all(action["completion_units"] == 1 for action in action_dispositions)
    assert all(action["score_effect_before_closeout"] == "none" for action in action_dispositions)
    assert all(row["competency_count"] > 0 for row in report["lever_coverage"])
    assert all(row["competency_count"] > 0 for row in report["family_coverage"])
    assert all(row["competency_count"] > 0 for row in report["domain_coverage"])


def test_composite_catalog_relationships_and_closeout_schedules_are_exact():
    report = _report()

    for row in report["competencies"]:
        relationships = row["relationships"]
        assert [action["action_id"] for action in row["action_dispositions"]] == row["action_ids"]
        assert sum(Decimal(item["blended_weight"]) for item in relationships) == 1
        assert sum(Decimal(value) for value in row["family_allocation"].values()) == 1
        equal_share = Decimal("1") / Decimal(len(relationships))
        for relationship in relationships:
            expected = (
                Decimal("0.50") * Decimal(relationship["canonical_weight"])
                + Decimal("0.50") * equal_share
            )
            assert abs(Decimal(relationship["blended_weight"]) - expected) <= Decimal(
                "0.000000000001"
            )
        assert row["score_trigger"] == "explicit_human_final_closeout"
        assert row["check_in_score_effect"] == "none"
        assert row["credit_schedule"][0]["completed_actions"] == row["minimum_completed"]
        assert row["credit_schedule"][0]["completion_credit"] == "0.750000000000"
        assert row["credit_schedule"][-1]["completed_actions"] == row["total_actions"]
        assert row["credit_schedule"][-1]["completion_credit"] == "1.000000000000"


def test_composite_catalog_hash_verifies():
    report = _report()
    expected = report.pop("report_hash")

    assert canonical_hash(report) == expected
