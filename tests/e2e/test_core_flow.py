import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from growth.models import (
    AssessmentCalibrationConsent,
    AssessmentRun,
    CompletionCreditEvent,
    EvidenceEvent,
    PersonalOSRevision,
    PilotFeedback,
    PracticeCheckIn,
    PracticeContext,
    PracticeProtocol,
    PracticeSprint,
    WeeklyExecutionPlan,
    WeeklyExecutionReview,
)
from growth.services.assessment import encode_share_code, load_assessment_assets
from growth.services.canonical_import import seed_canonical_data
from growth.services.practice import start_practice
from growth.services.score_state import synchronize_all_score_states

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "assessment" / "v1.1_bundle" / "grounded_growth_assessment_v1_1"
LEGACY_GGA1_CODE = (
    "GGA1.eyJ2IjoiMS4wIiwiciI6IjU1MzQ0MzQyNDI0NDQ0MzMyMzQzMjQzNTQ0NDQzNDU0"
    "NDQzMjIyMzQ0NDMzMzE0NDM0IiwiZSI6eyJDX0wzNCI6MiwiQ19MMzUiOjMsIkNfTDA1"
    "Ijo0LCJDX0wwOSI6MywiQ19MMTkiOjQsIkNfTDI2IjoyLCJDX0wwOCI6MywiQ19MMTciOj"
    "R9LCJ0Ijo0MC43ODc5OTk5OTk5OTk5OH0="
)

PROTOCOL_WALKTHROUGH = (
    (
        "deepen-one-existing-friendship",
        "Deepen One Existing Friendship",
        "Check-ins preserve evidence but do not update completion credit.",
    ),
    (
        "schedule-non-instrumental-play",
        "Schedule Non-Instrumental Play",
        "Check-ins preserve evidence but do not update completion credit.",
    ),
    (
        "practice-emotional-cue-detection",
        "Practice Emotional Cue Detection",
        "Check-ins preserve evidence but do not update completion credit.",
    ),
    (
        "state-and-maintain-one-boundary",
        "State and Maintain One Boundary",
        "Check-ins preserve evidence but do not update completion credit.",
    ),
    (
        "complete-an-attention-presence-experiment",
        "Complete an Attention-Presence Experiment",
        "Check-ins preserve evidence but do not update completion credit.",
    ),
)


def create_browser_user():
    return get_user_model().objects.create_user(
        username="grounded",
        password="Browser-Test-Password-2047!",
    )


def seed_browser_data():
    seed_canonical_data()
    synchronize_all_score_states()


def log_in(live_server, page):
    page.goto(f"{live_server.url}/")
    page.get_by_label("Username").fill("grounded")
    page.get_by_label("Password").fill("Browser-Test-Password-2047!")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(f"{live_server.url}/")


def wait_for_assessment_save(page):
    status = page.locator("#assessment-save-status")
    expect(status).to_have_text(re.compile(r"Saved|Already saved|Save failed"))
    assert status.inner_text() != "Save failed", page.locator("#assessment-save-error").inner_text()


def open_assessment(live_server, page):
    page.get_by_role("link", name="Assessment", exact=True).click()
    page.wait_for_url(f"{live_server.url}/assessment/")
    page.wait_for_load_state("load")
    expect(page.locator("#assessment-app")).to_be_visible()
    assert page.evaluate("typeof window.GroundedGrowthAssessment") == "object"
    assert page.evaluate("typeof window.GroundedGrowthAssessmentApp") == "object"


def assert_no_horizontal_overflow(page):
    overflow = page.evaluate(
        """() => ({
            documentFits: document.documentElement.scrollWidth <= window.innerWidth,
            offenders: [...document.querySelectorAll('body *')]
                .filter((element) => {
                    const rect = element.getBoundingClientRect();
                    return rect.right > window.innerWidth + 1 || rect.left < -1;
                })
                .slice(0, 8)
                .map((element) => ({
                    tag: element.tagName.toLowerCase(),
                    id: element.id,
                    className: String(element.className || ''),
                    text: String(element.textContent || '').trim().slice(0, 80),
                    left: Math.round(element.getBoundingClientRect().left),
                    right: Math.round(element.getBoundingClientRect().right),
                })),
        })"""
    )
    assert overflow["documentFits"], (
        f"Page has horizontal overflow at {page.viewport_size}: {overflow['offenders']}"
    )


def save_walkthrough_screenshot(page, name, *, full_page=True):
    path = ROOT / "test-results" / "pilot-walkthrough" / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=path, full_page=full_page)


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_login_home_and_profile_core_flow(live_server, page: Page):
    create_browser_user()
    seed_browser_data()

    log_in(live_server, page)
    assert page.url == f"{live_server.url}/"
    page.get_by_role("heading", name="No practice in progress").wait_for()
    page.get_by_text("Deepen One Existing Friendship", exact=True).wait_for()
    page.get_by_role("link", name="View developmental profile").click()

    page.wait_for_url(f"{live_server.url}/profile/")
    page.get_by_role("heading", name="A provisional map, not an identity.").wait_for()
    page.get_by_text("The Seeker", exact=True).wait_for()
    page.get_by_text(
        re.compile(r"completion remains separate from mastery", re.IGNORECASE),
    ).wait_for()


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_mobile_keyboard_walkthrough_covers_all_active_protocols(live_server, page: Page):
    page.set_viewport_size({"width": 390, "height": 844})
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.goto(f"{live_server.url}/")
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Skip to main content")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#main-content")).to_be_focused()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-home")

    page.get_by_role("link", name="Practices", exact=True).click()
    expect(page.locator(".practice-card")).to_have_count(383)
    expect(page.locator('.practice-card[data-availability="active"]')).to_have_count(383)
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-practice-library", full_page=False)

    for slug, name, score_boundary in PROTOCOL_WALKTHROUGH:
        page.goto(f"{live_server.url}/practices/{slug}/")
        page.get_by_role("heading", name=name, exact=True).wait_for()
        page.get_by_text("You will not need to invent the practice.").wait_for()
        assert_no_horizontal_overflow(page)

        page.get_by_role("link", name="Start guided setup").click()
        page.get_by_text(score_boundary).wait_for()
        page.get_by_role("button", name="Continue").wait_for()
        assert_no_horizontal_overflow(page)
        save_walkthrough_screenshot(page, f"mobile-{slug}-setup")

    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/profile/")
    page.get_by_role("heading", name="A provisional map, not an identity.").wait_for()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "desktop-profile")

    for slug, name, _score_boundary in PROTOCOL_WALKTHROUGH:
        page.goto(f"{live_server.url}/practices/{slug}/")
        page.get_by_role("heading", name=name, exact=True).wait_for()
        assert_no_horizontal_overflow(page)
        save_walkthrough_screenshot(page, f"desktop-{slug}")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_personal_os_context_priority_alternative_private_accessible_journey(
    live_server,
    page: Page,
):
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)
    sentinel = "SYNTHETIC-PRIVATE-M6C04-BROWSER"

    page.get_by_role("link", name="Personal OS", exact=True).click()
    page.get_by_role("heading", name="Choose what guides this season.").wait_for()
    page.get_by_text("included in normal database backups").wait_for()
    assert_no_horizontal_overflow(page)
    page.get_by_label(
        "Response state for: What purpose or contribution do you choose to orient toward for now?"
    ).select_option("provided")
    page.get_by_label(
        "What purpose or contribution do you choose to orient toward for now?",
        exact=True,
    ).fill(sentinel)
    page.get_by_role("button", name="Save Personal OS revision").click()
    page.get_by_text("Personal OS revision saved.").wait_for()
    assert PersonalOSRevision.objects.count() == 1

    page.get_by_label("Current season response state").select_option("provided")
    page.get_by_label("Current season:", exact=True).select_option("transition")
    page.get_by_label("Capacity response state").select_option("provided")
    page.get_by_label("Room for one additional bounded practice").select_option("4")
    page.get_by_role("button", name="Save season and capacity").click()
    page.get_by_text("Season and capacity revision saved.").wait_for()
    save_walkthrough_screenshot(page, "mobile-personal-os-synthetic")

    first = "deepen-one-existing-friendship"
    second = "schedule-non-instrumental-play"
    page.goto(f"{live_server.url}/practices/{first}/")
    page.get_by_role("button", name="Not applicable to me — show an alternative").click()
    page.get_by_text("Practice context revision saved.").wait_for()
    page.get_by_role("heading", name="Ask for a distinct reviewed alternative").wait_for()
    page.goto(f"{live_server.url}/profile/")
    page.get_by_text("Personal-applicable coverage view").wait_for()
    page.get_by_text("382", exact=True).wait_for()
    page.get_by_text("canonical all-competency coverage, unchanged").wait_for()
    assert_no_horizontal_overflow(page)
    page.goto(f"{live_server.url}/personal-os/practices/{first}/context/")
    page.get_by_role("button", name="Request alternative").click()
    page.get_by_text("No other explicitly reviewed practice").wait_for()

    page.goto(f"{live_server.url}/personal-os/practices/{second}/context/")
    page.get_by_label("Provide all six context factors").check()
    for label, value in (
        ("Fit with your present role and situation", "4"),
        ("Current importance among competing goods", "3"),
        ("Readiness to attempt this bounded practice", "4"),
        ("User-reported time sensitivity", "2"),
        ("Available opportunity, support, access, and resources", "3"),
        ("Expected time, access, effort, emotional, relational, or material load", "1"),
    ):
        page.get_by_label(label).select_option(value)
    page.get_by_role("button", name="Save practice context").click()
    assert PracticeContext.objects.count() == 2

    page.goto(f"{live_server.url}/personal-os/practices/{first}/context/")
    page.get_by_role("button", name="Request alternative").click()
    page.get_by_text("Schedule Non-Instrumental Play", exact=True).wait_for()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-context-alternative-synthetic")

    page.goto(f"{live_server.url}/personal-os/practices/{second}/context/")
    page.get_by_label("Provide all six context factors").check()
    for label in (
        "Fit with your present role and situation",
        "Current importance among competing goods",
        "Readiness to attempt this bounded practice",
        "User-reported time sensitivity",
        "Available opportunity, support, access, and resources",
        "Expected time, access, effort, emotional, relational, or material load",
    ):
        page.get_by_label(label).select_option("")
    page.get_by_role("button", name="Save practice context").click()
    expect(page.get_by_label("Fit with your present role and situation")).to_be_focused()

    page.goto(f"{live_server.url}/")
    assert sentinel not in page.locator("body").inner_text()
    page.get_by_text("Current context fit is available.").wait_for()
    assert_no_horizontal_overflow(page)
    page.evaluate("document.body.style.zoom = '200%'")
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-context-home-200-percent")
    page.evaluate("document.body.style.zoom = ''")

    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/practices/")
    page.get_by_role("heading", name="Not ranked by current context").wait_for()
    assert sentinel not in page.locator("body").inner_text()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "desktop-context-ranking-synthetic")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_weekly_execution_plans_one_action_and_reviews_only_existing_proof(
    live_server,
    page: Page,
):
    page.set_viewport_size({"width": 390, "height": 844})
    user = create_browser_user()
    seed_browser_data()
    sprint = start_practice(
        user=user,
        protocol=PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01"),
        person_or_context="Synthetic browser weekly context",
        start_date=date.today(),
    )
    action = sprint.protocol.actions.order_by("sequence").first()
    log_in(live_server, page)

    page.get_by_role("link", name="Weekly", exact=True).click()
    page.get_by_role("heading", name="Turn one direction into one concrete action.").wait_for()
    page.get_by_text("One operating loop, no hidden analysis.").wait_for()
    page.get_by_label("One action to make concrete this week").select_option(action.pk)
    page.get_by_role("button", name="Save weekly plan").click()
    page.get_by_text("Weekly plan revision saved.").wait_for()
    page.get_by_text("No submitted proof for this plan").wait_for()
    assert WeeklyExecutionPlan.objects.count() == 1
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-weekly-plan")

    page.get_by_label("Continue the current action").check()
    page.get_by_label(
        "What adjustment, if any, would make the next attempt more workable?"
    ).select_option("none")
    page.get_by_role("button", name="Save proof-based weekly review").click()
    page.get_by_text("Weekly proof review saved.").wait_for()
    page.get_by_text("The review created no new evidence or score contribution.").wait_for()
    assert WeeklyExecutionReview.objects.get().outcome == "no_submitted_evidence"
    assert EvidenceEvent.objects.count() == 0

    page.evaluate("document.body.style.zoom = '200%'")
    assert_no_horizontal_overflow(page)
    page.evaluate("document.body.style.zoom = ''")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/weekly/")
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "desktop-weekly-review")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_owner_data_management_is_private_accessible_and_requires_exact_confirmation(
    live_server,
    page: Page,
):
    page.set_viewport_size({"width": 390, "height": 844})
    user = create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.get_by_role("link", name="Account", exact=True).click()
    page.get_by_role("heading", name="Keep control of your private record.").wait_for()
    page.get_by_role("heading", name="Optional assessment calibration contribution").wait_for()
    page.get_by_text("The demonstration seed is never eligible.").wait_for()
    page.get_by_text("Retention is disabled by default.").wait_for()
    page.get_by_text("Existing backups may still contain prior copies").wait_for()
    expect(page.locator(".practice-card")).to_have_count(0)
    assert "383-item" not in page.locator("body").inner_text()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-owner-data-management")

    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download owner-private archive").click()
    payload = json.loads(Path(download_info.value.path()).read_text())
    assert payload["privacy_class"] == "owner-private"
    assert payload["privacy"]["safe_for_sharing"] is False
    assert payload["account"]["username"] == "grounded"
    assert user.password not in json.dumps(payload)

    page.get_by_label("Current password").fill("Browser-Test-Password-2047!")
    page.get_by_label(re.compile(r'Type "DELETE MY ACCOUNT"')).fill("DO NOT DELETE")
    page.get_by_role("button", name="Permanently delete account").click()
    page.get_by_text("The account-deletion confirmation text does not match.").wait_for()
    assert get_user_model().objects.filter(pk=user.pk).exists()

    page.keyboard.press("Control+Home")
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Skip to main content")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#main-content")).to_be_focused()
    page.evaluate("document.body.style.zoom = '200%'")
    assert_no_horizontal_overflow(page)
    page.evaluate("document.body.style.zoom = ''")

    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/account/data/")
    page.get_by_role("heading", name="Keep control of your private record.").wait_for()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "desktop-owner-data-management")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_optional_pilot_feedback_is_local_minimized_and_score_separate(
    live_server,
    page: Page,
):
    page.set_viewport_size({"width": 390, "height": 844})
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.get_by_role("link", name="Account", exact=True).click()
    page.get_by_role("link", name="Open feedback form").click()
    page.get_by_role("heading", name="Tell the pilot what got in the way.").wait_for()
    page.get_by_text("This is usability feedback, not developmental evidence.").wait_for()
    page.get_by_text("No automatic timing or remote telemetry").wait_for()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-pilot-feedback")

    page.get_by_label("Which part are you commenting on?").select_option("assessment")
    expect(page.get_by_label("Practice, if relevant")).to_be_hidden()
    expect(
        page.get_by_label("Roughly how long did setup take before you could begin?")
    ).to_be_hidden()
    expect(page.get_by_label("Roughly how long did a check-in take?")).to_be_hidden()

    page.get_by_label("Which part are you commenting on?").select_option("check_in")
    expect(page.get_by_label("Practice, if relevant")).to_be_visible()
    expect(page.get_by_label("Roughly how long did a check-in take?")).to_be_visible()
    page.get_by_label("Practice, if relevant").select_option("PRACTICE-FRIENDSHIP-01")
    page.get_by_label("Did the recommendation fit your current situation?").select_option("partly")
    page.get_by_label("Roughly how long did setup take before you could begin?").select_option(
        "2_to_5_minutes"
    )
    page.get_by_label("Roughly how long did a check-in take?").select_option("1_to_2_minutes")
    page.get_by_label("Which step was most confusing?").select_option("setup")
    page.get_by_label(
        "Did an accessibility need make the application harder to use?"
    ).select_option("none")
    page.get_by_label(
        "Did any instruction or interaction feel unsafe or poorly bounded?"
    ).select_option("none")
    page.get_by_label("Optional detail").fill("PRIVATE-BROWSER-FEEDBACK-TOKEN")
    page.get_by_role("button", name="Submit optional feedback").click()
    page.get_by_text(
        "Optional product feedback submitted. It did not change your profile or practice."
    ).wait_for()
    assert PilotFeedback.objects.count() == 1

    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download minimized JSON").click()
    payload = json.loads(Path(download_info.value.path()).read_text())
    assert payload["record_count"] == 1
    assert payload["remote_telemetry_used"] is False
    assert payload["developmental_state_modified_by_feedback"] is False
    assert "PRIVATE-BROWSER-FEEDBACK-TOKEN" not in json.dumps(payload)

    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/account/pilot-feedback/")
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "desktop-pilot-feedback")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_play_protocol_setup_is_specific_and_score_active(live_server, page: Page):
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.goto(f"{live_server.url}/practices/schedule-non-instrumental-play/")
    page.get_by_role("heading", name="Schedule Non-Instrumental Play").wait_for()
    page.get_by_text("You will not need to invent the practice.").wait_for()
    page.get_by_role("link", name="Start guided setup").click()
    page.get_by_text("Check-ins preserve evidence but do not update completion credit").wait_for()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Yes, this activity or context is available").check()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Private label for the person or context").fill("tabletop game")
    page.get_by_role("button", name="Continue").click()
    page.get_by_label(
        "I will keep this activity safe, voluntary, and proportionate to my responsibilities."
    ).check()
    page.get_by_role("button", name=re.compile(r"I understand")).click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="I have reviewed the defined actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("A specific play window was reserved").wait_for()
    expect(page.get_by_label("I engaged in the activity")).to_be_hidden()
    expect(page.get_by_label("I returned to play within seven days")).to_be_hidden()
    assert page.get_by_label("Expected reciprocity").count() == 0
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Submit check-in").click()
    page.get_by_text("Submit evidence only after a real attempt.").wait_for()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-action-specific-check-in")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "cid,label,mixed,scope,reference,criterion,other_criterion",
    [
        (
            "13.05",
            "cooking",
            "Mixed: The food was prepared",
            "Scope: The skillet practices",
            "fsis.usda.gov",
            "Ingredients and equipment are ready",
            "Heat and moisture are adjusted to observations",
        ),
        (
            "02.01",
            "ethics",
            "Mixed: Four frameworks were named",
            "Scope: One case introduces",
            "openstax.org",
            "Four lenses supply distinct reasons",
            "Authority and legitimate claims are considered",
        ),
        (
            "05.04",
            "personality",
            "Mixed: The label predicted one situation",
            "Scope: This tests one practical prediction",
            "simine.com",
            "A label becomes a context specific prediction",
            "Two opportunities are described with their conditions",
        ),
        (
            "05.07",
            "feedback",
            "Mixed: The feedback was summarized accurately",
            "Scope: One person's observation supplies a perspective",
            "simine.com",
            "Feedback is voluntary and about one shared event",
            "The giver can correct the summary",
        ),
        (
            "03.02",
            "wisdom-study",
            "Mixed: The primary passages and practice were examined",
            "Scope: This is a small study unit",
            "classics.mit.edu",
            "Primary passages have retrievable locations",
            "An exemplar is connected to a concrete teaching",
        ),
        (
            "03.03",
            "contemplation",
            "Mixed: The pause sometimes helped attention",
            "Scope: Five brief occasions provide an initial pattern",
            "nccih.nih.gov",
            "A cue and exact short sequence are defined",
            "Five opportunities are accounted for without inventing attempts",
        ),
        (
            "03.10",
            "shared-remembrance",
            "Mixed: A visitor understood the gathering better",
            "Scope: One permitted communal form is practiced",
            None,
            "The form has an identified tradition or honestly named shared story",
            "An actual communal occasion takes place",
        ),
        (
            "04.07",
            "moral-distress",
            "Mixed: The distinctions were clear",
            "Scope: This is literacy and support preparation using a fictional case",
            "ptsd.va.gov",
            "All six distinctions are explained without diagnosis",
            "Questions separate facts responsibility repair and support",
        ),
        (
            "04.08",
            "care-preferences",
            "Mixed: The private questions were ready",
            "Scope: This prepares a conversation",
            "medlineplus.gov",
            "Planning legal documentation and current treatment are distinguished",
            "The person chooses the kind and duration of company",
        ),
        (
            "06.02",
            "trauma-literacy",
            "Mixed: The glossary was accurate",
            "Scope: This is literacy and support preparation using a fictional case",
            "nimh.nih.gov",
            "All eight concepts receive a plain language explanation",
            "The response gives a choice about support",
        ),
        (
            "06.08",
            "receiving-care",
            "Mixed: The task was completed but the pause signal was missed",
            "Scope: One ordinary help agreement practices receiving care",
            "nhs.uk",
            "Decision choices and practical assistance are separated",
            "The agreement identifies task timing and helper limits",
        ),
        (
            "06.09",
            "access-redesign",
            "Mixed: The words were clearer",
            "Scope: A before-and-after information task demonstrates a bounded design change",
            "w3.org",
            "The five information needs are checked against the original",
            "A revised notice is actually produced",
        ),
        (
            "06.14",
            "professional-handoff",
            "Mixed: The emergency route was clear",
            "Scope: This is resource preparation and fictional response rehearsal",
            "nimh.nih.gov",
            "All seven categories have an appropriate boundary explanation",
            "Four types of help have location-appropriate public routes",
        ),
    ],
)
def test_tailored_practices_show_readable_scope_examples_and_observation_checks(
    live_server, page: Page, cid, label, mixed, scope, reference, criterion, other_criterion
):
    user = create_browser_user()
    seed_browser_data()
    log_in(live_server, page)
    protocol = PracticeProtocol.objects.get(parent_competency_id=cid)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{live_server.url}/practices/{protocol.slug}/")
    page.get_by_role("heading", name=protocol.name, exact=True).wait_for()
    expect(page.get_by_text(mixed, exact=False)).to_be_visible()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, f"mobile-tailored-{label}-actions")
    page.get_by_role("link", name="Start guided setup").click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Yes, this activity or context is available").check()
    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_text(scope, exact=False)).to_be_visible()
    if reference is not None:
        expect(
            page.get_by_role("link", name=re.compile(re.escape(reference))).first
        ).to_be_visible()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, f"mobile-tailored-{label}-setup")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context=f"Synthetic {label} demonstration",
        start_date=date.today(),
    )
    page.goto(f"{live_server.url}/practice-sprints/{sprint.pk}/")
    page.get_by_role("link", name="Add compact check-in").click()
    checks = page.get_by_role(
        "group",
        name=f"Observed checks: {protocol.actions.get(sequence=1).title.lower()}",
        exact=True,
    )
    expect(checks).to_be_visible()
    expect(checks.get_by_label(criterion, exact=True)).to_be_visible()
    expect(page.get_by_label(other_criterion, exact=True)).to_be_hidden()
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, f"mobile-tailored-{label}-observations")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/practices/{protocol.slug}/")
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, f"desktop-tailored-{label}-actions")


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_emotional_cue_setup_and_check_in_are_bounded(live_server, page: Page):
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.goto(f"{live_server.url}/practices/practice-emotional-cue-detection/")
    page.get_by_role("heading", name="Practice Emotional Cue Detection").wait_for()
    page.get_by_text("Notice before interpreting").wait_for()
    page.get_by_role("link", name="Start guided setup").click()
    page.get_by_text("Check-ins preserve evidence but do not update completion credit").wait_for()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Yes, this activity or context is available").check()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Private label for the person or context").fill("weekly project sync")
    page.get_by_role("button", name="Continue").click()
    page.get_by_text("Observation is not mind-reading.").wait_for()
    page.get_by_label(
        "I will treat cues as uncertain, avoid diagnosis and stereotyping, "
        "and prefer direct clarification over assumption."
    ).check()
    page.get_by_role("button", name=re.compile(r"I understand")).click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="I have reviewed the defined actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("I deliberately paused to observe before interpreting").wait_for()
    page.get_by_label("I noticed an observable change without assigning a motive").wait_for()
    expect(page.get_by_label("I asked a neutral question to check my impression")).to_be_hidden()
    assert page.get_by_label("Expected reciprocity").count() == 0
    assert page.get_by_label("A specific future interaction was scheduled").count() == 0


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_boundary_setup_and_check_in_are_safe_and_specific(live_server, page: Page):
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.goto(f"{live_server.url}/practices/state-and-maintain-one-boundary/")
    page.get_by_role("heading", name="State and Maintain One Boundary").wait_for()
    page.get_by_text("Define what you control").wait_for()
    page.get_by_role("link", name="Start guided setup").click()
    page.get_by_text("Check-ins preserve evidence but do not update completion credit").wait_for()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Yes, one safe, low-stakes situation is likely to arise").check()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Private label for the person or context").fill("after-hours requests")
    page.get_by_role("button", name="Continue").click()
    page.get_by_text("A boundary is not coercion or punishment.").wait_for()
    page.get_by_text("unsafe dependency, or retaliation").wait_for()
    page.get_by_label(
        "I will use a low-stakes context where direct communication is reasonably "
        "safe, state only what I control, and not use threats, punishment, silent "
        "tests, or pressure."
    ).check()
    page.get_by_role("button", name=re.compile(r"I understand")).click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="I have reviewed the defined actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("I chose a specific limit and a response that I control").wait_for()
    page.get_by_label("I stated the boundary directly in specific words").wait_for()
    expect(
        page.get_by_label("I checked understanding without bargaining or testing")
    ).to_be_hidden()
    expect(
        page.get_by_label(
            "I followed through proportionately or restated the boundary within seven days"
        )
    ).to_be_hidden()
    assert page.get_by_label("Expected reciprocity").count() == 0
    assert page.get_by_label("Observed reciprocity").count() == 0
    assert (
        page.get_by_label("Personally meaningful information was voluntarily shared").count() == 0
    )


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_presence_setup_and_check_in_are_accessible_and_specific(live_server, page: Page):
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.goto(f"{live_server.url}/practices/complete-an-attention-presence-experiment/")
    page.get_by_role("heading", name="Complete an Attention-Presence Experiment").wait_for()
    page.get_by_text("Run the usual-condition window").wait_for()
    page.get_by_role("link", name="Start guided setup").click()
    page.get_by_text("Check-ins preserve evidence but do not update completion credit").wait_for()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Yes, I have a safe 15-minute activity I can repeat").check()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Private label for the person or context").fill("technical reading")
    page.get_by_role("button", name="Continue").click()
    page.get_by_text("Presence is not stillness, perfection, or surveillance.").wait_for()
    page.get_by_text("disability, neurodiversity, pain, fatigue").wait_for()
    page.get_by_label(
        "I will use a safe, low-stakes activity, keep supports and alerts needed "
        "for access or safety, and treat distraction as information—not failure."
    ).check()
    page.get_by_role("button", name=re.compile(r"I understand")).click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="I have reviewed the defined actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("I noticed attention drift and deliberately returned").wait_for()
    expect(page.get_by_label("I compared the usual and changed condition")).to_be_hidden()
    expect(
        page.get_by_label("I repeated the more workable condition within seven days")
    ).to_be_hidden()
    assert page.get_by_label("Expected reciprocity").count() == 0
    assert page.get_by_label("Observed reciprocity").count() == 0
    assert page.get_by_label("A specific future interaction was scheduled").count() == 0


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_complete_assessment_and_save_canonical_outputs(live_server, page: Page):
    user = create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    open_assessment(live_server, page)
    page.get_by_role("button", name="Begin assessment").click()
    for index in range(50):
        expect(page.locator("#assessment-count")).to_have_text(f"{index + 1} of 50")
        answer = ("1" if index % 2 == 0 else "5") if index < 12 else "4"
        page.get_by_role("button", name=re.compile(rf"^{answer} —")).click()
        page.get_by_role(
            "button",
            name="Finish" if index == 49 else "Next",
            exact=True,
        ).click()
    page.get_by_role("button", name="Answer targeted clarifiers").click()
    clarifier_count = int(page.locator("#assessment-count").inner_text().split()[-1])
    assert 1 <= clarifier_count <= 10
    for index in range(clarifier_count):
        page.get_by_role("button", name=re.compile(r"^4 —")).click()
        page.get_by_role(
            "button",
            name="Finish" if index == clarifier_count - 1 else "Next",
            exact=True,
        ).click()
    page.get_by_role("heading", name="Your working profile").wait_for()
    wait_for_assessment_save(page)
    assert page.locator("#assessment-share-code").input_value().startswith("GGA11.")

    run = AssessmentRun.objects.filter(user=user, source=AssessmentRun.Source.APPLICATION).get()
    assert len(run.answers) == 50
    assert any(item_id.startswith("O_") for item_id in run.clarifier_answers)
    assert run.orientation_results.count() == 6
    assert run.archetype_results.count() == 15
    assert run.lever_baselines.count() == 37
    assert not run.lever_baselines.filter(
        baseline_alpha__isnull=True,
    ).exists()

    page.get_by_role("link", name="Account", exact=True).click()
    page.get_by_role("heading", name="Optional assessment calibration contribution").wait_for()
    page.get_by_label(re.compile(r"I understand the calibration contribution")).check()
    page.get_by_label(re.compile(r"I consent to this completed assessment")).check()
    page.get_by_role("button", name="Include this assessment").click()
    page.get_by_text("Assessment calibration consent recorded.").wait_for()
    assert (
        AssessmentCalibrationConsent.objects.filter(
            assessment_run=run,
            state=AssessmentCalibrationConsent.State.CONSENTED,
        ).count()
        == 1
    )

    with page.expect_download() as download_info:
        page.get_by_role("link", name="Inspect my exact contribution").click()
    contribution = json.loads(Path(download_info.value.path()).read_text())
    assert contribution["assessment_run_count"] == 1
    assert contribution["participant_evidence_axes_completed"] == 0
    assert run.original_share_code not in json.dumps(contribution)

    page.get_by_role("button", name="Withdraw from future exports").click()
    page.get_by_text("Assessment calibration consent withdrawn").wait_for()
    assert AssessmentCalibrationConsent.objects.filter(assessment_run=run).count() == 2


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_import_gga11_and_supported_gga1(live_server, page: Page):
    user = create_browser_user()
    seed_browser_data()
    input_data = json.loads((BUNDLE / "pilot_001_responses_v1_compatible.json").read_text())
    current_code = encode_share_code(
        load_assessment_assets().spec,
        input_data["responses"],
        total_seconds=sum(input_data["timings_seconds"].values()),
    )
    log_in(live_server, page)

    open_assessment(live_server, page)
    page.get_by_label("Share code", exact=True).fill(current_code)
    page.get_by_role("button", name="Import profile").click()
    wait_for_assessment_save(page)
    page.get_by_role("button", name="Retake").click()

    page.get_by_label("Share code", exact=True).fill(LEGACY_GGA1_CODE)
    page.get_by_role("button", name="Import profile").click()
    wait_for_assessment_save(page)

    imported = AssessmentRun.objects.filter(
        user=user,
        source=AssessmentRun.Source.SHARE_CODE,
    )
    assert imported.count() == 2
    assert imported.filter(original_share_code__startswith="GGA11.").exists()
    assert imported.filter(original_share_code__startswith="GGA1.").exists()


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_guided_practice_draft_pause_and_completion_flow(live_server, page: Page):
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.get_by_role("link", name="Practices", exact=True).click()
    page.get_by_role("link", name="Review protocol").first.click()
    page.get_by_role("heading", name="Deepen One Existing Friendship").wait_for()
    page.get_by_text("You will not need to invent the practice.").wait_for()
    page.get_by_role("link", name="Start guided setup").click()

    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Yes, this relationship is available").check()
    page.get_by_role("button", name="Continue").click()
    page.get_by_label("Private label for the person or context").fill("R.")
    page.get_by_role("button", name="Continue").click()
    page.get_by_label(re.compile(r"I will choose welcome contact")).check()
    page.get_by_role(
        "button",
        name="I understand and will respect these boundaries",
    ).click()
    page.get_by_label("Start date").fill(date.today().isoformat())
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="I have reviewed the defined actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("heading", name="Deepen One Existing Friendship").wait_for()

    page.get_by_role("button", name="Pause practice").click()
    page.get_by_role("button", name="Resume practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("Which action is this about?").select_option(
        label="Action 1: Listen to what matters now"
    )
    page.get_by_label("Action attempted").check()
    page.get_by_label("Action completed").check()
    page.get_by_label("The interaction moved beyond logistics or small talk").check()
    page.get_by_label("Meaningful information was freely shared").check()
    page.get_by_role("button", name="Save draft").click()
    page.get_by_role("heading", name="Draft check-ins").wait_for()
    assert PracticeCheckIn.objects.filter(status=PracticeCheckIn.Status.SUBMITTED).count() == 0

    page.locator(".draft-list a").click()
    page.get_by_label("How much support did you use?").select_option("independent")
    page.get_by_label("What direction did the observation point?").select_option("supports")
    page.get_by_role("button", name="Submit check-in").click()
    page.get_by_text("Check-in submitted and added to evidence history.").wait_for()
    page.get_by_role("link", name="Listen to what matters now").click()
    page.get_by_role("heading", name="Listen to what matters now").wait_for()
    page.get_by_text("This observation is proof, not a global score update.").wait_for()
    page.get_by_text("Technical audit details").click()
    page.get_by_text("GG-EVIDENCE-1.0").wait_for()
    page.get_by_role("link", name="Evidence", exact=True).click()
    page.wait_for_url(f"{live_server.url}/evidence/")
    page.get_by_role("heading", name="What your check-ins recorded.").wait_for()
    page.get_by_text("Structured observations, with private context removed").wait_for()
    page.get_by_role("listitem").get_by_text("Supported expected pattern", exact=True).wait_for()
    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download privacy-safe JSON").click()
    exported = json.loads(Path(download_info.value.path()).read_text())
    assert exported["event_count"] == 1
    assert exported["profile_scores_modified"] is False
    assert exported["profile_scores_modified_by_export"] is False
    page.get_by_role("link", name="Read evidence explanation").click()
    page.get_by_role("heading", name="Listen to what matters now").wait_for()
    page.get_by_role("link", name="Profile", exact=True).click()
    page.get_by_role("heading", name="What completed practices have changed").wait_for()
    page.get_by_text("Closeout contract · versioned").wait_for()
    page.get_by_text(
        re.compile(r"Check-ins remain immutable proof but do not change this state"),
    ).wait_for()
    page.go_back()
    page.get_by_role("heading", name="Listen to what matters now").wait_for()
    page.get_by_role("link", name=re.compile(r"Deepen One Existing Friendship")).click()

    for label, completed in (
        ("Action 2: Make a specific invitation", True),
        ("Action 3: Follow up", False),
    ):
        page.get_by_role("link", name="New check-in").click()
        page.get_by_label("Which action is this about?").select_option(label=label)
        page.get_by_label("Action attempted").check()
        if completed:
            page.get_by_label("Action completed").check()
        page.get_by_label("How much support did you use?").select_option("independent")
        page.get_by_label("How does this setting compare with earlier check-ins?").select_option(
            "same_context"
        )
        page.get_by_label("What direction did the observation point?").select_option("supports")
        page.get_by_role("button", name="Submit check-in").click()

    page.get_by_role("link", name="Review and close").click()
    page.get_by_text("Completing this practice does not establish mastery.").wait_for()
    page.get_by_label("What did this practice show you?").fill(
        "Specific invitations made the next step clearer."
    )
    page.get_by_role(
        "button",
        name="Submit final review and record 75% credit",
    ).click()
    page.get_by_role("heading", name="The experiment is closed.").wait_for()
    page.get_by_text("Completing this practice does not establish mastery.").wait_for()
    assert PracticeSprint.objects.get().status == PracticeSprint.Status.COMPLETED
    assert CompletionCreditEvent.objects.get().completion_credit == Decimal("0.7500")
