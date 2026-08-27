#!/usr/bin/env python3
# ruff: noqa: E501
"""Materialize and activate the complete 383/383 competency runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRACTICE_ROOT = ROOT / "data" / "practices"
CURRICULUM_PATH = (
    ROOT / "data" / "curriculum" / "ideal_person_curriculum_v2_pluralist_full_scope.yaml"
)
MODEL_PATH = ROOT / "data" / "model" / "grounded_growth_model_v1.json"
MANIFEST_PATH = PRACTICE_ROOT / "release_manifest.yaml"
ACTIVATION_PATH = PRACTICE_ROOT / "registries" / "activation_ledger.yaml"
SOURCE_PATH = PRACTICE_ROOT / "registries" / "source_registry.yaml"

CANONICAL_SOURCE_ID = "SRC-CANONICAL-CURRICULUM-V2"
GLOBAL_GAP_IDS = ["RG-M6A-001", "RG-M6A-002"]
GLOBAL_REVIEW_IDS = ["ER-M6A-003"]
ACTIVE_SCORING_POLICY_ID = "SP-STRUCTURED-EVIDENCE-ELIGIBLE"
SCORE_STATE_CONTRACT = "GG-SCORE-STATE-1.0"
TYPED_RUNTIME_PROJECTION = "GG-PRACTICE-RUNTIME-PROJECTION-2.0"
LEGACY_RUNTIME_PROJECTION = "GG-PRACTICE-RUNTIME-PROJECTION-1.0"
ACTIVATION_DECISION = "docs/PRODUCT_DECISIONS.md#decision-052"

# These packages predate the full-frontier batch and remain byte-for-byte
# authoritative. Every other canonical competency is materialized by this
# script under a deterministic PRACTICE-COMP-* stable ID.
PRESERVED_PARENT_IDS = {
    "08.02",
    "08.06",
    "09.12",
    "10.02",
    "11.10",
    "13.02",
    "16.03",
    "17.03",
    "26.01",
}

HIGH_RISK_DOMAINS = {"06", "07", "12", "15", "18", "19", "23", "24"}
MODERATE_RISK_DOMAINS = {"02", "04", "13", "14", "16", "17", "20", "21", "22", "26"}
HIGH_RISK_TERMS = {
    "abuse",
    "addiction",
    "bereavement",
    "child protection",
    "chronic illness",
    "chronic pain",
    "consent",
    "death",
    "dementia",
    "dying",
    "emergency",
    "end-of-life",
    "fertility",
    "financial hardship",
    "grief",
    "medical",
    "mental health",
    "moral injury",
    "pregnancy",
    "reproductive",
    "self-harm",
    "sexual",
    "substance",
    "suicide",
    "trauma",
    "violence",
}
SAFETY_TERMS = {
    "bystander",
    "cybersecurity",
    "disaster",
    "emergency",
    "fire",
    "first aid",
    "fraud",
    "preparedness",
    "rescue",
    "risk",
    "safety",
    "security",
    "survival",
    "violence",
}
RELATIONAL_TERMS = {
    "apology",
    "belonging",
    "caregiving",
    "collaboration",
    "communication",
    "conflict",
    "conversation",
    "courtship",
    "family",
    "feedback",
    "friendship",
    "hospitality",
    "intercultural",
    "listening",
    "mentorship",
    "negotiation",
    "parenting",
    "partnership",
    "repair",
    "support",
}
COMMUNITY_TERMS = {
    "citizenship",
    "community",
    "mutual aid",
    "neighborhood",
    "public service",
    "social movement",
    "volunteering",
}
LONGITUDINAL_TERMS = {
    "annual",
    "changing",
    "development",
    "life review",
    "long-term",
    "maintenance",
    "pattern",
    "recurring",
    "season",
    "transition",
}
CONTEMPLATIVE_TERMS = {
    "awe",
    "contemplation",
    "faith",
    "flourishing",
    "gratitude",
    "hope",
    "meaning",
    "metaphysical",
    "mortality",
    "prayer",
    "purpose",
    "reverence",
    "ritual",
    "sacred",
    "spiritual",
    "worldview",
}

FAMILY_LABELS = {
    "PF-ARTIFACT-PLAN": "artifact-and-review practice",
    "PF-AUDIT-REDESIGN": "bounded audit and redesign",
    "PF-BEHAVIORAL-EXPERIMENT": "bounded behavioral experiment",
    "PF-COMMUNITY-CONTRIBUTION": "consent-based community contribution",
    "PF-CONTEMPLATIVE-MEANING": "pluralist meaning practice",
    "PF-KNOWLEDGE-APPLICATION": "knowledge-and-application practice",
    "PF-LONGITUDINAL-REVIEW": "bounded longitudinal review",
    "PF-QUALIFIED-CONSULTATION": "qualified-support preparation",
    "PF-RELATIONAL-CONVERSATION": "consent-respecting relational practice",
    "PF-REPEATED-HABIT": "small repeated practice",
    "PF-SAFETY-PREPARATION": "non-confrontational safety preparation",
    "PF-SKILL-REHEARSAL": "low-stakes skill rehearsal",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected one mapping")
    return value


def _yaml_bytes(value: dict[str, Any]) -> bytes:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    ).encode()


def _slug(value: str) -> str:
    normalized = value.encode("ascii", "ignore").decode().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or "practice"


def _contains_any(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _risk_class(domain_id: str, competency: dict[str, Any]) -> str:
    text = " ".join([competency["name"], competency["scope"], competency["evidence_of_progress"]])
    if domain_id in HIGH_RISK_DOMAINS or _contains_any(text, HIGH_RISK_TERMS):
        return "RISK-HIGH"
    if domain_id in MODERATE_RISK_DOMAINS:
        return "RISK-MODERATE"
    return "RISK-LOW"


def _protocol_family(
    domain_id: str,
    competency: dict[str, Any],
    risk_class: str,
) -> str:
    text = " ".join([competency["name"], competency["scope"]])
    evidence_types = set(competency["measurement"]["preferred_evidence_types"])
    if risk_class == "RISK-HIGH":
        return (
            "PF-SAFETY-PREPARATION"
            if _contains_any(text, SAFETY_TERMS)
            else "PF-QUALIFIED-CONSULTATION"
        )
    if domain_id == "03" or _contains_any(text, CONTEMPLATIVE_TERMS):
        return "PF-CONTEMPLATIVE-MEANING"
    if _contains_any(text, COMMUNITY_TERMS):
        return "PF-COMMUNITY-CONTRIBUTION"
    if _contains_any(text, RELATIONAL_TERMS):
        return "PF-RELATIONAL-CONVERSATION"
    if _contains_any(text, LONGITUDINAL_TERMS):
        return "PF-LONGITUDINAL-REVIEW"
    if evidence_types & {"performance_task", "audience_feedback"}:
        return "PF-SKILL-REHEARSAL"
    if evidence_types & {"objective_indicator", "outcome_indicator"}:
        return "PF-AUDIT-REDESIGN"
    if evidence_types & {"artifact", "reflective_artifact"}:
        return "PF-ARTIFACT-PLAN"
    if evidence_types & {"behavioral_adherence", "real_world_application"}:
        return "PF-REPEATED-HABIT"
    if "conceptual_explanation" in evidence_types:
        return "PF-KNOWLEDGE-APPLICATION"
    return "PF-BEHAVIORAL-EXPERIMENT"


def _family_actions(
    family_id: str,
    *,
    name: str,
    scope: str,
    evidence: str,
) -> list[tuple[str, str, str, tuple[str, ...]]]:
    actions: dict[str, list[tuple[str, str, str, tuple[str, ...]]]] = {
        "PF-KNOWLEDGE-APPLICATION": [
            (
                f"Map the core distinctions in {name}",
                f"Create a compact concept map for {name}. Use this canonical scope as the boundary: {scope} Separate the central idea, at least one competing interpretation, one practical implication, and one uncertainty; do not present the map as expert certification.",
                "conceptual",
                (
                    "central_idea_distinguished",
                    "competing_view_represented",
                    "uncertainty_recorded",
                ),
            ),
            (
                f"Apply {name} to one low-stakes case",
                f"Choose one fictional, public, or safely de-identified case where {name} matters. Apply the distinctions from the concept map, state which facts are missing, and compare the reasoning with this evidence target: {evidence}",
                "scenario",
                ("case_bounded", "concept_applied", "missing_facts_preserved"),
            ),
            (
                f"Correct the {name} explanation",
                f"Review the concept map and case together. Revise one overstatement, omitted limit, or unsupported inference so the final explanation of {name} remains consistent with: {evidence}",
                "artifact",
                ("revision_identified", "limit_preserved", "practical_implication_retained"),
            ),
        ],
        "PF-ARTIFACT-PLAN": [
            (
                f"Define a rubric for {name}",
                f"Turn the canonical scope for {name} into three to five inspectable criteria: {scope} Keep the rubric bounded to one current context and include one criterion for uncertainty, access, or competing obligations.",
                "artifact",
                ("criteria_trace_to_scope", "context_bounded", "constraint_included"),
            ),
            (
                f"Build one {name} artifact",
                f"Create the smallest useful plan, checklist, diagram, record, or other artifact that applies the rubric for {name}. Store only category-level information and omit names, secrets, credentials, diagnoses, protected work detail, and unnecessary third-party information.",
                "artifact",
                ("artifact_matches_rubric", "minimum_private_detail", "usable_next_step_present"),
            ),
            (
                f"Stress-test and revise the {name} artifact",
                f"Test the artifact against one realistic variation, counterexample, or changed constraint. Revise it only where the test exposes a gap, then compare the result with this evidence target: {evidence}",
                "scenario",
                ("variation_tested", "revision_traceable", "target_evidence_compared"),
            ),
        ],
        "PF-AUDIT-REDESIGN": [
            (
                f"Audit one bounded {name} context",
                f"Inspect one user-controlled, low-consequence context relevant to {name}. Use the canonical scope to name observable conditions without diagnosing people or systems: {scope}",
                "artifact",
                ("one_context_only", "observable_conditions_recorded", "hazards_excluded"),
            ),
            (
                f"Make one reversible {name} redesign",
                f"Choose one small, lawful, reversible change that addresses a specific audit finding for {name}. Record the intended effect, cost or burden, and a rollback condition before changing anything.",
                "artifact",
                ("change_traces_to_finding", "rollback_defined", "burden_recorded"),
            ),
            (
                f"Compare the {name} context after the change",
                f"Reinspect the same bounded context after the change. Record improvement, no difference, mixed effects, harm, or insufficient observation and compare only with this target: {evidence}",
                "artifact",
                (
                    "same_context_compared",
                    "mixed_or_null_result_allowed",
                    "target_evidence_reviewed",
                ),
            ),
        ],
        "PF-RELATIONAL-CONVERSATION": [
            (
                f"Prepare a consent-safe {name} interaction",
                f"Choose one welcome, low-stakes relationship context for {name}. Translate the canonical scope into one observable communication act, identify power or retaliation concerns, and obtain or preserve the other person's freedom not to participate: {scope}",
                "artifact",
                ("communication_act_specific", "consent_boundary_present", "power_checked"),
            ),
            (
                f"Practice one {name} communication act",
                f"Use the prepared {name} act once without covert testing, pressure, diagnosis, deception inference, or a demand for disclosure. Ask one direct clarification when appropriate and allow refusal, delay, indirect communication, language access, or another format.",
                "boolean",
                ("communication_act_attempted",),
            ),
            (
                f"Review {name} without scoring the person",
                f"Review only the observable interaction and its boundaries. Do not infer motives or store private narrative. Compare what happened with this evidence target and retain disagreement or an inconclusive result: {evidence}",
                "artifact",
                (
                    "observable_interaction_reviewed",
                    "private_narrative_excluded",
                    "inconclusive_allowed",
                ),
            ),
        ],
        "PF-REPEATED-HABIT": [
            (
                f"Define one small {name} behavior",
                f"Choose one voluntary, reversible behavior that represents a narrow part of {name}. Bound the cue, context, duration, and valid interruption using this scope: {scope}",
                "artifact",
                ("behavior_observable", "cue_and_context_defined", "interruption_valid"),
            ),
            (
                f"Try the {name} behavior in three windows",
                f"Attempt the same small {name} behavior in up to three naturally occurring windows. Record attempt, defer, interruption, support used, and adverse effect separately; never manufacture deprivation, distress, conflict, or unsafe conditions to obtain a repetition.",
                "count",
                ("bounded_attempt_count",),
            ),
            (
                f"Review the {name} repetition pattern",
                f"Compare the windows for feasibility, burden, context, and interruption. Keep missing or mixed evidence explicit and compare the limited pattern with this evidence target: {evidence}",
                "artifact",
                ("windows_distinguished", "burden_compared", "transfer_not_assumed"),
            ),
        ],
        "PF-SKILL-REHEARSAL": [
            (
                f"Define observable criteria for {name}",
                f"Select one safe, lawful, low-stakes component of {name}. Build a three-to-five-item rubric from this scope, including an error or stop criterion: {scope}",
                "artifact",
                ("skill_component_bounded", "observable_rubric_present", "error_or_stop_defined"),
            ),
            (
                f"Rehearse {name} twice",
                f"Perform two bounded attempts of the selected {name} component under comparable safe conditions. Use self-review, a consensual observer, or a reviewed artifact; do not require public exposure, coerced feedback, licensed work, or high-consequence performance.",
                "count",
                ("bounded_attempt_count",),
            ),
            (
                f"Use feedback for one {name} retry",
                f"Choose one rubric item that remained weak, make one specific adjustment, and retry only that component. Preserve no-change or worse results and compare the evidence with: {evidence}",
                "artifact",
                ("feedback_item_selected", "adjustment_traceable", "retry_result_preserved"),
            ),
        ],
        "PF-CONTEMPLATIVE-MEANING": [
            (
                f"Choose a declared frame for {name}",
                f"Select a religious, spiritual, philosophical, cultural, or secular frame through which to explore {name}. State the frame, one alternative, and the limits of personal authority using this canonical scope: {scope}",
                "conceptual",
                ("frame_declared", "alternative_acknowledged", "authority_limited"),
            ),
            (
                f"Complete two bounded {name} practices",
                f"Complete two short, freely chosen {name} practices appropriate to the declared frame, such as reading, silence, prayer, observation, ritual, dialogue, or reflection. Stop for distress, coercion, altered-state risk, conscience conflict, or pressure from an authority or group.",
                "count",
                ("bounded_practice_count",),
            ),
            (
                f"Interpret the {name} experience modestly",
                f"Review what was noticed without treating intensity, calm, certainty, group agreement, or unusual experience as automatic truth. Compare the limited record with this evidence target: {evidence}",
                "artifact",
                (
                    "experience_and_interpretation_separated",
                    "alternative_explanation_retained",
                    "target_evidence_compared",
                ),
            ),
        ],
        "PF-COMMUNITY-CONTRIBUTION": [
            (
                f"Listen for a bounded {name} need",
                f"Identify one need related to {name} through a public request, authorized contact, or community-defined priority. Verify who has authority to set scope and avoid extracting private stories or assuming outsiders know the need: {scope}",
                "artifact",
                ("need_community_defined", "authority_identified", "private_story_not_required"),
            ),
            (
                f"Agree and complete one {name} contribution",
                f"Agree on one limited {name} contribution, its owner, time boundary, access needs, and exit condition. Complete only the agreed scope without replacing local leadership, creating dependency, claiming representation, or escalating conflict.",
                "boolean",
                ("agreed_contribution_completed",),
            ),
            (
                f"Review the {name} contribution with proportionate feedback",
                f"Obtain minimal, freely given feedback from an authorized recipient or use an objective completion indicator. Record benefit, burden, no effect, harm, or unknown and compare only with: {evidence}",
                "artifact",
                (
                    "feedback_proportionate",
                    "burden_or_harm_recorded",
                    "community_ownership_preserved",
                ),
            ),
        ],
        "PF-QUALIFIED-CONSULTATION": [
            (
                f"Bound the qualified question for {name}",
                f"Turn {name} into one educational or planning question and identify the qualification and jurisdiction needed to answer it. Use the canonical scope to separate general learning from diagnosis, treatment, legal advice, financial advice, safeguarding decisions, or other professional judgment: {scope}",
                "artifact",
                ("question_bounded", "qualification_named", "professional_boundary_explicit"),
            ),
            (
                f"Prepare minimum information for {name}",
                f"Create a privacy-minimized {name} consultation note containing only the question, relevant category-level facts, current constraints, and desired decision. Omit diagnoses, allegations, account numbers, credentials, protected work information, intimate detail, and third-party identity unless a qualified professional lawfully requires it through an appropriate channel.",
                "artifact",
                ("minimum_information_only", "sensitive_detail_excluded", "decision_need_named"),
            ),
            (
                f"Record a bounded {name} disposition",
                f"Use an appropriately qualified source or consultation to record only a next-step category: proceed within stated limits, seek a different qualification, gather missing information, defer, or use urgent support. Do not store professional narrative or convert the disposition into mastery. Target evidence remains: {evidence}",
                "attestation",
                ("qualified_disposition_recorded",),
            ),
        ],
        "PF-SAFETY-PREPARATION": [
            (
                f"Identify the non-emergency boundary for {name}",
                f"Define one planning-only question for {name}, the hazards that must not be rehearsed, and the local qualified or emergency authority that supersedes this source-only protocol. Do not create, approach, or simulate danger: {scope}",
                "artifact",
                ("planning_scope_bounded", "hazards_excluded", "authority_identified"),
            ),
            (
                f"Prepare one safe {name} support step",
                f"Create one non-confrontational {name} step such as locating official guidance, checking accessible contact information, assembling a category-level checklist, or scheduling qualified instruction. Do not test emergency response, weapons, rescue, medical treatment, confrontation, evasion, or hazardous equipment.",
                "artifact",
                ("step_is_preparatory", "official_or_qualified_path_used", "no_hazard_rehearsed"),
            ),
            (
                f"Review the {name} plan against stop conditions",
                f"Check whether the plan identifies when to stop, leave, call emergency services, contact a qualified professional, or follow local authority. Mark unknown requirements rather than inventing them and compare only with: {evidence}",
                "scenario",
                ("stop_conditions_present", "escalation_path_present", "unknowns_retained"),
            ),
        ],
        "PF-LONGITUDINAL-REVIEW": [
            (
                f"Define indicators for {name}",
                f"Choose two to four observable, privacy-minimized indicators for {name}, plus a missing-data rule and one contradiction indicator. Bound the review to one role or context using this scope: {scope}",
                "artifact",
                (
                    "indicators_observable",
                    "missing_data_rule_present",
                    "contradiction_indicator_present",
                ),
            ),
            (
                f"Observe {name} across three checkpoints",
                f"Collect up to three brief {name} checkpoints across the selected period or contexts. Record unknown, not observed, not applicable, defer, and adverse outcomes as valid states; do not infer a trend from prose length, mood, or one unusually good or bad event.",
                "count",
                ("bounded_checkpoint_count",),
            ),
            (
                f"Review the limited {name} pattern",
                f"Compare the checkpoints, name the strongest contradiction or missing context, and choose repeat, adapt, stop, or seek support. Treat this target as a review criterion rather than proof of transfer: {evidence}",
                "artifact",
                ("checkpoints_compared", "contradiction_or_gap_named", "transfer_limit_preserved"),
            ),
        ],
        "PF-BEHAVIORAL-EXPERIMENT": [
            (
                f"Define one bounded {name} comparison",
                f"Choose one safe, voluntary, low-stakes situation relevant to {name}. Define a usual condition, one reversible changed condition, and one observable result using this scope: {scope}",
                "artifact",
                ("usual_condition_defined", "changed_condition_reversible", "result_observable"),
            ),
            (
                f"Try the changed {name} condition once",
                f"Run the changed {name} condition once only when the situation occurs naturally and remains safe. Record attempt, defer, interruption, support, no effect, and harm without increasing stakes or withholding needed resources.",
                "boolean",
                ("changed_condition_attempted",),
            ),
            (
                f"Compare the bounded {name} result",
                f"Compare the usual and changed conditions without attributing the result to character or broad capability. Preserve confounds and an inconclusive outcome, and compare the record with: {evidence}",
                "artifact",
                ("conditions_compared", "confounds_retained", "broad_transfer_not_claimed"),
            ),
        ],
    }
    return actions[family_id]


def _measurement(
    *,
    measurement_id: str,
    kind: str,
    role: str,
    token: str,
    criteria: tuple[str, ...],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "measurement_id": measurement_id,
        "kind": kind,
        "role": role,
        "weight": "1" if role == "primary" else ("0.5" if role == "supporting" else "0"),
        "allowed_provenance": [
            "qualified_attestation"
            if kind == "attestation"
            else ("firsthand_self_report" if kind in {"boolean", "count"} else "reviewed_artifact")
        ],
    }
    if kind == "boolean":
        value["expected"] = True
    elif kind in {"count", "bounded_frequency"}:
        value.update(direction="at_least", minimum="0", target="1", maximum="3")
    elif kind in {"artifact", "conceptual", "scenario"}:
        value["criteria"] = [f"{token}_{criterion}" for criterion in criteria]
    elif kind == "attestation":
        value["allowed_attestation_ids"] = [f"{token}_qualified_disposition"]
        value["consent_required"] = True
    else:
        raise ValueError(f"Unsupported generated measurement kind: {kind}")
    return value


def _build_actions(
    *,
    stable_id: str,
    competency_id: str,
    policy_id: str,
    family_id: str,
    name: str,
    scope: str,
    evidence: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, str], list[str]]:
    token = f"c{competency_id.replace('.', '')}"
    actions: list[dict[str, Any]] = []
    check_in_fields: list[str] = []
    labels: dict[str, str] = {}
    primary_ids: list[str] = []
    for index, (title, instructions, kind, criteria) in enumerate(
        _family_actions(family_id, name=name, scope=scope, evidence=evidence), start=1
    ):
        action_id = f"{stable_id}-A{index}"
        action_token = f"{token}_a{index}"
        primary_id = f"{action_token}_primary"
        boundary_id = f"{action_token}_boundary"
        adverse_id = f"{action_token}_adverse"
        measurements = [
            _measurement(
                measurement_id=primary_id,
                kind=kind,
                role="primary",
                token=action_token,
                criteria=criteria,
            ),
            _measurement(
                measurement_id=boundary_id,
                kind="boolean",
                role="supporting",
                token=action_token,
                criteria=(),
            ),
            _measurement(
                measurement_id=adverse_id,
                kind="boolean",
                role="adverse",
                token=action_token,
                criteria=(),
            ),
        ]
        actions.append(
            {
                "stable_id": action_id,
                "sequence": index,
                "title": title,
                "instructions": instructions,
                "expected_time": "15-25 minutes",
                "due_within_days": (3, 7, 10)[index - 1],
                "typed_evidence_identity": {
                    "protocol_stable_id": stable_id,
                    "action_stable_id": action_id,
                    "competency_stable_id": competency_id,
                    "scoring_policy_id": policy_id,
                },
                "evidence_rules": {
                    "schema_version": "typed-evidence-rules-v1",
                    "max_age_days": 90,
                    "competency_measurement_ids": [primary_id],
                    "transfer_disposition": "context_bound",
                    "measurements": measurements,
                },
            }
        )
        check_in_fields.extend([primary_id, boundary_id, adverse_id])
        labels.update(
            {
                primary_id: f"The bounded {name} criterion for action {index} was observed",
                boundary_id: f"Action {index} stayed inside its stated {name} boundary",
                adverse_id: f"Action {index} produced harm, pressure, or a boundary violation",
            }
        )
        primary_ids.append(primary_id)
    return actions, check_in_fields, labels, primary_ids


def _build_protocol(
    *,
    domain: dict[str, Any],
    competency: dict[str, Any],
    lever_ids: list[str],
    display_order: int,
) -> dict[str, Any]:
    competency_id = competency["id"]
    compact_id = competency_id.replace(".", "")
    name = competency["name"]
    scope = competency["scope"]
    evidence = competency["evidence_of_progress"]
    risk_class = _risk_class(domain["id"], competency)
    family_id = _protocol_family(domain["id"], competency, risk_class)
    stable_id = f"PRACTICE-COMP-{compact_id}-{_slug(name).upper()}-01"
    policy_id = ACTIVE_SCORING_POLICY_ID
    scoring_status = "active"
    actions, fields, labels, primary_ids = _build_actions(
        stable_id=stable_id,
        competency_id=competency_id,
        policy_id=policy_id,
        family_id=family_id,
        name=name,
        scope=scope,
        evidence=evidence,
    )
    applicability = competency["classification"]["applicability"]
    boundary = domain.get("professional_boundary")
    boundary_text = (
        boundary
        or "Use qualified, local, or emergency support whenever the situation exceeds a voluntary low-stakes developmental practice."
    )
    family_label = FAMILY_LABELS[family_id]
    role_condition = f"This competency is {applicability.replace('_', ' ')}; roles, duties, and authority must be explicitly chosen or actually held before the practice applies."
    high_risk = risk_class == "RISK-HIGH"
    return {
        "schema_version": "GG-PRACTICE-CONTENT-1.0",
        "protocol_version": "0.1.0",
        "stable_id": stable_id,
        "slug": f"c{compact_id}-{_slug(name)}-practice",
        "name": f"Bounded {name} Practice",
        "parent_competency_id": competency_id,
        "domain_id": domain["id"],
        "governance": {
            "availability": "active",
            "editorial_status": "draft",
            "runtime_projection": TYPED_RUNTIME_PROJECTION,
            "risk_class_id": risk_class,
            "scoring_policy_id": policy_id,
            "scoring_status": scoring_status,
            "source_ids": [CANONICAL_SOURCE_ID],
            "authoring": {
                "provenance": (
                    f"Individually materialized source-only frontier package for canonical competency {competency_id} ({name}); canonical scope, evidence target, classification, domain boundary, and parent mapping remain explicit and reviewable."
                ),
                "content_review_status": "pending",
                "research_review_status": "internal_sources_only_external_review_required",
                "safety_review_status": (
                    "pending_specialist_expansion_review" if high_risk else "pending"
                ),
                "accessibility_review_status": "pending",
                "originality_review_status": "pending",
                "ui_test_status": "not_applicable",
                "last_reviewed": None,
                "known_gap_ids": GLOBAL_GAP_IDS,
                "expert_review_ids": GLOBAL_REVIEW_IDS,
            },
            "legacy_compatibility_exceptions": [],
            "deprecation": {"deprecated": False, "replaced_by": None},
        },
        "meaning_and_fit": {
            "purpose": (
                f"Practice {name} through a {family_label} bounded by the canonical scope: {scope}"
            ),
            "why_recommended": (
                f"The parent competency identifies this limited evidence target: {evidence} The protocol creates a small opportunity to examine that target without treating completion as broad capability."
            ),
            "claims": [
                {
                    "statement": (
                        f"Using the canonical scope and evidence target for {name} is a traceable product-design basis for a source-only draft protocol."
                    ),
                    "classification": "product_design_judgment",
                    "source_ids": [CANONICAL_SOURCE_ID],
                    "limitations": (
                        "The canonical curriculum is not empirical intervention validation, a professional standard, a diagnosis, a universal prescription, or evidence that this exact protocol improves the competency."
                    ),
                }
            ],
            "applicability_question": (
                f"Does a voluntary, bounded {name} practice fit the person's current role, pathway, capacity, authority, resources, and safety conditions?"
            ),
            "not_applicable_behavior": (
                f"Record {name} as not applicable, consciously unchosen, or deferred without penalty when the role, pathway, capacity, authority, opportunity, or safe context is absent."
            ),
            "readiness_considerations": (
                f"Proceed only when the person can freely choose a limited {name} context, understand the source-only status, and stop without losing safety, care, employment, housing, services, relationship access, or dignity."
            ),
            "opportunity_considerations": (
                f"Use one naturally available low-stakes opportunity relevant to {name}; do not manufacture conflict, deprivation, exposure, disclosure, danger, urgency, or dependence for evidence."
            ),
            "prerequisites": [
                f"One user-chosen context that genuinely fits the canonical scope of {name}.",
                "Enough authority, consent, capacity, and resources to stop or defer safely.",
            ],
            "dependencies": [],
            "safe_alternatives": [
                f"Use a fictional, public, retrospective, or category-level case for {name} instead of a live situation.",
                "Defer, reduce scope, use an accessible equivalent, or seek appropriate support without a deficit interpretation.",
            ],
            "role_conditions": [role_condition],
            "pathway_conditions": [
                f"Religious, secular, cultural, disability-adapted, collective, and individual pathways may express {name} differently while preserving consent, evidence limits, safety, and equal dignity."
            ],
            "worldview_conditions": [
                f"The practice does not require one worldview or treat disagreement about {name} as inferiority; competing reasonable interpretations and conscientious refusal remain visible."
            ],
        },
        "intervention": {
            "protocol_class": family_id,
            "duration_days": 10,
            "cadence": (
                f"Complete three bounded {name} actions over ten days, preserving explicit not-applicable, defer, interruption, adverse, and unknown outcomes."
            ),
            "setup": (
                f"Choose one context for {name}; copy the canonical scope and evidence target into a private working note; define the action boundary, valid supports, privacy limit, and stop condition before beginning."
            ),
            "privacy_and_boundaries": (
                f"Store only allowlisted criteria and category-level observations for {name}. Do not store private prose, names, identities, diagnoses, allegations, credentials, account data, protected work information, intimate detail, artifact contents, observer narrative, or another person's secrets. This source-only draft is not surveillance, professional advice, treatment, certification, or proof of character."
            ),
            "expected_burden": (
                f"About 45-75 minutes total across setup, three {name} actions, and review; scope may be reduced or deferred for access, care, health, workload, conscience, or resource reasons."
            ),
            "action_count_rationale": None,
            "foreseeable_misuse": [
                f"Using the {name} protocol to rank worth, coerce participation, demand disclosure, override rest or care, certify competence, or justify decisions beyond the recorded context.",
                f"Treating a completed {name} action, a polished artifact, agreement, confidence, speed, independence, or output as mastery or universal transfer.",
            ],
            "exclusions": [
                f"Any {name} situation involving emergency response, abuse, retaliation, illegal conduct, medical treatment, legal representation, financial-loss decisions, safeguarding, hazardous equipment, or other consequences beyond a reversible source-only exercise.",
                boundary_text,
            ],
            "actions": actions,
            "adaptations": {
                "low_resource": [
                    f"Use paper, an offline note, a library resource, a public example, or a no-cost conversation for {name}; no purchase, subscription, travel, credential, or public artifact is required."
                ],
                "accessibility": [
                    f"Change timing, duration, medium, language, sensory load, location, posture, response mode, or support level for {name}; assistive technology, interpretation, a support person, and a deferred action are valid without penalty."
                ],
                "cultural_context": [
                    f"Adapt the expression of {name} to direct or indirect communication, collective or individual decision structures, local norms, faith or secular commitments, and role obligations while preserving consent and dignity."
                ],
                "resource_variants": [
                    f"When a real {name} opportunity is unavailable or inappropriate, use a fictional, historical, public, simulated, or planning-only equivalent and retain the narrower evidence classification."
                ],
            },
            "pause_conditions": [
                f"Pause {name} when capacity, consent, authority, privacy, access, care duties, uncertainty, distress, fatigue, pain, resource scarcity, or changed circumstances make the next action unwise."
            ],
            "stop_conditions": [
                f"Stop the {name} practice for harm, coercion, retaliation risk, emergency conditions, unsafe exposure, worsening symptoms, protected information, legal or policy conflict, or pressure to exceed the stated boundary."
            ],
            "escalation_conditions": [
                f"Use the appropriate local safeguarding, emergency, organizational, legal, medical, financial, accessibility, or other qualified channel when a {name} situation exceeds a voluntary low-stakes practice."
            ],
            "professional_referral_conditions": [boundary_text],
        },
        "evidence_and_scoring": {
            "accepted_evidence_types": [
                f"structured criteria observations for the bounded {name} actions",
                "explicit contradiction, adverse, defer, not-applicable, and unknown states",
            ],
            "observation_contract_version": "typed-evidence-rules-v1",
            "check_in_fields": fields,
            "adverse_or_contradictory_indicators": [
                f"The {name} action exceeded consent, authority, privacy, qualification, role, burden, or safety boundaries.",
                f"The evidence contradicted the intended {name} criterion, depended on coercion or hidden private content, or could not distinguish the protocol from contextual change.",
            ],
            "independence_rule": (
                f"Record self-directed, planning-aid, guided, artifact, observer, or qualified support for {name} explicitly; support can enable access and never reduces dignity or silently changes the typed value."
            ),
            "context_transfer_rule": (
                f"Evidence remains limited to the chosen {name} context, action, role, pathway, and assessment epoch; it does not establish cross-context reliability."
            ),
            "repetition_rule": (
                f"Each {name} observation requires a distinct immutable origin; duplicate origins are rejected and later repetitions use the typed contract's explicit diminishing multipliers."
            ),
            "recency_rule": (
                f"Generated {name} rules withhold observations older than 90 days; no unrecorded retention or carry-forward assumption applies."
            ),
            "performance_rubric": (
                f"Performance concerns only the action-specific criteria derived from the canonical target—{evidence}—not completion, confidence, conformity, output, independence, or worth."
            ),
            "evidence_quality_rubric": (
                f"Quality for {name} requires a bounded context, allowlisted observations, provenance, contradiction and adverse handling, and preserved uncertainty; free text and artifact contents are excluded."
            ),
            "scoring_eligibility": (
                "Replay-verified structured evidence is score eligible under the explicit activation ledger; withholding rules still apply to each event."
            ),
            "competency_contribution": (
                f"Designated primary measurements may produce one context-bound direct {name} contribution under typed evaluation; protocol performance remains distinct and is never counted twice."
            ),
            "canonical_lever_allocation": "parent_competency_mapping",
            "recommendation_target_lever_ids": lever_ids,
            "minimum_evidence_before_state_update": (
                f"A current-state update requires a submitted replay-verified {name} event with an observed competency measurement and no applicable withholding condition."
            ),
            "withholding_conditions": [
                f"Withhold unattempted, unknown, not-observed, not-applicable, deferred, inconclusive, stale, duplicate-origin, or adverse {name} evidence.",
                "Withhold any record containing private narrative, artifact contents, another person's identity, unsupported inference, or evidence outside its assessment epoch.",
            ],
        },
        "completion_and_review": {
            "completion_criteria": [
                f"The {actions[0]['title'].lower()} action was attempted or explicitly deferred.",
                f"The {actions[1]['title'].lower()} action was attempted or explicitly deferred.",
                f"The {actions[2]['title'].lower()} action preserved a limited conclusion, contradiction, or inconclusive result.",
            ],
            "completion_rules": {
                "minimum_completed": 2,
                "substantive_markers": primary_ids,
                "marker_mode": "any",
            },
            "mastery_disclaimer": "Completing this practice does not establish mastery.",
            "progression_criteria": (
                f"Repeat or broaden {name} only when the initial context remained safe, the evidence criteria were usable, burden was acceptable, and a new context can be named without assuming transfer."
            ),
            "transfer_limit": (
                f"Three bounded actions do not establish {name} across roles, cultures, relationships, seasons, stress levels, disability states, institutions, or high-consequence settings."
            ),
            "reflection": {
                "before": (
                    f"What does {name} require in this exact context, what remains outside my role or authority, and which scope sentence or evidence criterion will keep the practice honest?"
                ),
                "during": (
                    f"Which observable {name} criterion is present, absent, mixed, or unknown, and are consent, privacy, access, burden, and stop conditions still intact?"
                ),
                "after": (
                    f"How did the result compare with '{evidence}', what contradiction or missing context matters most, and should this {name} design be repeated, adapted, deferred, stopped, or referred?"
                ),
            },
            "review_guidance": {
                "repeat": f"Repeat the same bounded {name} design only when the context and burden remain appropriate.",
                "adapt": f"Change the {name} medium, scope, support, timing, criteria, or context while preserving provenance and the narrower evidence claim.",
                "stop": f"Stop {name} when the practice becomes coercive, unsafe, privacy-invasive, role-inappropriate, professionally restricted, or harmful.",
                "escalate": f"Use appropriate qualified or emergency support for {name} questions beyond this educational source-only boundary.",
            },
            "evidence_examples": {
                "supportive": (
                    f"The bounded {name} criteria were observed with provenance and no adverse boundary signal in the selected context."
                ),
                "mixed": (
                    f"Some {name} criteria were observed while burden, support, contextual change, or a contradiction limited the conclusion."
                ),
                "contradictory": (
                    f"The observed result opposed the intended {name} criterion, introduced harm or coercion, or showed the design was not workable."
                ),
                "inconclusive": (
                    f"The {name} action was deferred, not observed, not applicable, stale, insufficiently bounded, or too confounded to interpret."
                ),
            },
        },
        "presentation": {
            "setup_copy": {
                "context_heading": f"Choose one bounded context for {name}.",
                "boundary_heading": "Not applicable, defer, support, and stop decisions carry no deficit.",
                "timing_hint": "Use three short actions over ten days; do not manufacture an opportunity.",
                "applicability_heading": f"Confirm role, pathway, authority, consent, access, and safety for {name}.",
            },
            "check_in_labels": labels,
            "completion_copy": (
                f"Complete the bounded {name} review without claiming mastery, broad transfer, professional validation, or human-worth measurement."
            ),
            "plain_language_evidence": (
                f"The structured record shows what happened in one limited {name} practice, including support, contradiction, defer, no result, or harm."
            ),
            "display_order": display_order,
        },
    }


def _canonical_protocol_paths(protocols: list[dict[str, Any]]) -> list[str]:
    return sorted(
        f"protocols/{protocol['domain_id']}/{protocol['stable_id']}.yaml" for protocol in protocols
    )


def _activate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    """Apply the owner-directed runtime and score contract without claiming review."""

    governance = protocol["governance"]
    evidence = protocol["evidence_and_scoring"]
    governance["availability"] = "active"
    governance["runtime_projection"] = (
        LEGACY_RUNTIME_PROJECTION
        if evidence["observation_contract_version"] == "practice-observation-v1"
        else TYPED_RUNTIME_PROJECTION
    )
    governance["scoring_policy_id"] = ACTIVE_SCORING_POLICY_ID
    governance["scoring_status"] = "active"
    evidence["scoring_eligibility"] = (
        "Replay-verified structured evidence is score eligible under the explicit "
        "activation ledger; action-specific provenance and withholding rules still apply."
    )
    evidence["minimum_evidence_before_state_update"] = (
        "One submitted replay-verified event with an observed competency measurement and "
        "no applicable withholding condition may update current state; completion alone never does."
    )
    protocol["presentation"]["completion_copy"] = (
        "Review the bounded evidence without claiming mastery, broad transfer, professional "
        "validation, identity, dignity, or human worth."
    )
    for action in protocol["intervention"]["actions"]:
        identity = action.get("typed_evidence_identity")
        if identity is not None:
            identity["scoring_policy_id"] = ACTIVE_SCORING_POLICY_ID
    return protocol


def _runtime_projection_hash(
    protocols: list[dict[str, Any]],
    activation: dict[str, Any],
) -> str:
    activation_by_id = {item["protocol_stable_id"]: item for item in activation["activations"]}
    payload = []
    for protocol in sorted(
        (
            item
            for item in protocols
            if item["stable_id"]
            in {
                "PRACTICE-BOUNDARY-01",
                "PRACTICE-EMOTIONAL-CUES-01",
                "PRACTICE-FRIENDSHIP-01",
                "PRACTICE-PLAY-01",
                "PRACTICE-PRESENCE-01",
            }
        ),
        key=lambda item: item["stable_id"],
    ):
        evidence = protocol["evidence_and_scoring"]
        review = protocol["completion_and_review"]
        presentation = protocol["presentation"]
        intervention = protocol["intervention"]
        governance = protocol["governance"]
        payload.append(
            {
                "stable_id": protocol["stable_id"],
                "slug": protocol["slug"],
                "name": protocol["name"],
                "parent_competency_id": protocol["parent_competency_id"],
                "availability": governance["availability"],
                "duration_days": intervention["duration_days"],
                "recommendation_reason": protocol["meaning_and_fit"]["why_recommended"],
                "applicability_prompt": protocol["meaning_and_fit"]["applicability_question"],
                "setup_prompt": intervention["setup"],
                "privacy_and_boundaries": intervention["privacy_and_boundaries"],
                "completion_criteria": review["completion_criteria"],
                "completion_rules": review["completion_rules"],
                "setup_copy": {
                    **presentation["setup_copy"],
                    "check_in_labels": presentation["check_in_labels"],
                },
                "check_in_fields": evidence["check_in_fields"],
                "score_active": activation_by_id[protocol["stable_id"]]["score_active"],
                "mastery_disclaimer": review["mastery_disclaimer"],
                "target_lever_ids": sorted(evidence["recommendation_target_lever_ids"]),
                "display_order": presentation["display_order"],
                "actions": [
                    {
                        "stable_id": action["stable_id"],
                        "sequence": action["sequence"],
                        "title": action["title"],
                        "instructions": action["instructions"],
                        "due_within_days": action["due_within_days"],
                        "evidence_rules": action["evidence_rules"],
                    }
                    for action in intervention["actions"]
                ],
            }
        )
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _content_hash(manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    projection = {key: value for key, value in manifest.items() if key != "content_hash"}
    digest.update(b"release_manifest.yaml\0")
    digest.update(json.dumps(projection, sort_keys=True, separators=(",", ":")).encode())
    digest.update(b"\0")
    for relative in sorted(manifest["content_files"]):
        path = PRACTICE_ROOT / relative
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _expected_documents() -> tuple[
    list[tuple[Path, bytes]],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
]:
    curriculum = _load_yaml(CURRICULUM_PATH)["curriculum"]
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    mappings = {
        item["competency_id"]: list(item["lever_weights"])
        for item in model["competency_lever_links"]
    }
    existing_manifest = _load_yaml(MANIFEST_PATH)
    preserved_paths = [PRACTICE_ROOT / relative for relative in existing_manifest["protocol_files"]]
    preserved_protocols = [
        _load_yaml(path)
        for path in preserved_paths
        if _load_yaml(path)["parent_competency_id"] in PRESERVED_PARENT_IDS
    ]
    if {item["parent_competency_id"] for item in preserved_protocols} != PRESERVED_PARENT_IDS:
        raise ValueError("The nine preserved competency packages are incomplete.")

    competency_rows = [
        (domain, competency)
        for domain in curriculum["domains"]
        for competency in domain["competencies"]
    ]
    if len(competency_rows) != 383:
        raise ValueError(f"Expected 383 competencies, found {len(competency_rows)}.")
    if set(mappings) != {competency["id"] for _, competency in competency_rows}:
        raise ValueError("Canonical competency-to-lever mappings do not cover the curriculum.")

    generated_protocols: list[dict[str, Any]] = []
    display_order = max(item["presentation"]["display_order"] for item in preserved_protocols) + 1
    for domain, competency in competency_rows:
        if competency["id"] in PRESERVED_PARENT_IDS:
            continue
        generated_protocols.append(
            _build_protocol(
                domain=domain,
                competency=competency,
                lever_ids=sorted(mappings[competency["id"]]),
                display_order=display_order,
            )
        )
        display_order += 1

    all_protocols = sorted(
        [_activate_protocol(protocol) for protocol in preserved_protocols + generated_protocols],
        key=lambda item: item["parent_competency_id"],
    )
    if len(all_protocols) != 383:
        raise ValueError(f"Expected 383 packages, found {len(all_protocols)}.")
    generated_files = [
        (
            PRACTICE_ROOT / "protocols" / protocol["domain_id"] / f"{protocol['stable_id']}.yaml",
            _yaml_bytes(protocol),
        )
        for protocol in all_protocols
    ]

    source_registry = _load_yaml(SOURCE_PATH)
    for source in source_registry["sources"]:
        if source["locator_kind"] == "repository_path":
            source["content_sha256"] = hashlib.sha256(
                (ROOT / source["locator"]).read_bytes()
            ).hexdigest()
    canonical_source = next(
        source
        for source in source_registry["sources"]
        if source["source_id"] == CANONICAL_SOURCE_ID
    )
    canonical_source["applicable_competency_ids"] = sorted(
        protocol["parent_competency_id"] for protocol in all_protocols
    )
    canonical_source["applicable_protocol_ids"] = sorted(
        protocol["stable_id"] for protocol in all_protocols
    )

    activation = _load_yaml(ACTIVATION_PATH)
    activation_entries = []
    for protocol in all_protocols:
        stable_id = protocol["stable_id"]
        activation_entries.append(
            {
                "protocol_stable_id": stable_id,
                "scoring_policy_id": ACTIVE_SCORING_POLICY_ID,
                "score_active": True,
                "activation_status": "active",
                "approved_contract": SCORE_STATE_CONTRACT,
                "decision_reference": ACTIVATION_DECISION,
                "shadow_test_status": "accepted_and_activated",
            }
        )
    activation["activations"] = sorted(
        activation_entries, key=lambda item: item["protocol_stable_id"]
    )

    manifest = _load_yaml(MANIFEST_PATH)
    # The release schema intentionally freezes this registry identity while
    # the source catalog expands additively.
    manifest["release_id"] = "M6A-CANONICAL-PRACTICE-FOUNDATION-1"
    manifest["protocol_files"] = _canonical_protocol_paths(all_protocols)
    static_content = [
        value for value in manifest["content_files"] if not value.startswith("protocols/")
    ]
    manifest["content_files"] = sorted(set(static_content + manifest["protocol_files"]))
    manifest["legacy_projection_hash"] = _runtime_projection_hash(all_protocols, activation)
    manifest["content_hash"] = "PENDING"
    return generated_files, source_registry, activation, all_protocols


def _write_or_check(check: bool) -> int:
    generated_files, source_registry, activation, all_protocols = _expected_documents()
    expected_files = dict(generated_files)
    expected_files[SOURCE_PATH] = _yaml_bytes(source_registry)
    expected_files[ACTIVATION_PATH] = _yaml_bytes(activation)

    manifest = _load_yaml(MANIFEST_PATH)
    manifest["release_id"] = "M6A-CANONICAL-PRACTICE-FOUNDATION-1"
    manifest["protocol_files"] = _canonical_protocol_paths(all_protocols)
    static_content = [
        value for value in manifest["content_files"] if not value.startswith("protocols/")
    ]
    manifest["content_files"] = sorted(set(static_content + manifest["protocol_files"]))
    manifest["legacy_projection_hash"] = _runtime_projection_hash(all_protocols, activation)
    manifest["content_hash"] = "PENDING"

    if not check:
        for path, content in expected_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        MANIFEST_PATH.write_bytes(_yaml_bytes(manifest))
        manifest["content_hash"] = _content_hash(manifest)
        MANIFEST_PATH.write_bytes(_yaml_bytes(manifest))
        print(
            "Authored 383/383 source packages: "
            f"{len(generated_files)} runtime and score active; "
            f"content hash {manifest['content_hash']}."
        )
        return 0

    stale = [
        path.relative_to(ROOT).as_posix()
        for path, expected in expected_files.items()
        if not path.is_file() or path.read_bytes() != expected
    ]
    if stale:
        print("Full-frontier authored files are stale:\n  " + "\n  ".join(stale))
        return 1
    expected_manifest = dict(manifest)
    expected_manifest["content_hash"] = _content_hash(manifest)
    if MANIFEST_PATH.read_bytes() != _yaml_bytes(expected_manifest):
        print("Full-frontier release manifest or content hash is stale.")
        return 1
    print("Full-frontier authored source is deterministic and current (383/383).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated source without writing files.",
    )
    args = parser.parse_args()
    try:
        return _write_or_check(args.check)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Full-frontier authoring failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
