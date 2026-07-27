from django.urls import path

from . import views, views_assessment, views_evidence, views_pilot, views_practice

app_name = "growth"

urlpatterns = [
    path("", views.home, name="home"),
    path("profile/", views.profile, name="profile"),
    path("evidence/", views_evidence.evidence_ledger, name="evidence-ledger"),
    path(
        "evidence/export.json",
        views_evidence.evidence_export,
        name="evidence-export",
    ),
    path(
        "account/pilot-feedback/",
        views_pilot.pilot_feedback,
        name="pilot-feedback",
    ),
    path(
        "account/pilot-feedback/export.json",
        views_pilot.pilot_feedback_export,
        name="pilot-feedback-export",
    ),
    path("assessment/", views_assessment.assessment, name="assessment"),
    path(
        "assessment/scoring-v1-1.js",
        views_assessment.assessment_scorer,
        name="assessment-scorer",
    ),
    path(
        "assessment/runs/",
        views_assessment.save_assessment,
        name="assessment-save",
    ),
    path("practices/", views_practice.practice_list, name="practice-list"),
    path(
        "practices/<slug:slug>/",
        views_practice.practice_recommendation,
        name="practice-recommendation",
    ),
    path(
        "practices/<slug:slug>/setup/<int:step>/",
        views_practice.practice_setup,
        name="practice-setup",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/",
        views_practice.practice_sprint,
        name="practice-sprint",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/state/",
        views_practice.practice_state,
        name="practice-state",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/check-ins/new/",
        views_practice.practice_check_in,
        name="practice-check-in-new",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/check-ins/<uuid:check_in_id>/",
        views_practice.practice_check_in,
        name="practice-check-in-edit",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/check-ins/<uuid:check_in_id>/evidence/",
        views_practice.practice_check_in_detail,
        name="practice-check-in-detail",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/review/",
        views_practice.practice_review,
        name="practice-review",
    ),
    path(
        "practice-sprints/<uuid:sprint_id>/review/complete/",
        views_practice.practice_review_complete,
        name="practice-review-complete",
    ),
]
