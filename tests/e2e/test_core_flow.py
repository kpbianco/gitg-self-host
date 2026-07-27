import json
import re
from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from growth.models import AssessmentRun, PracticeCheckIn, PracticeSprint
from growth.services.assessment import encode_share_code, load_assessment_assets
from growth.services.canonical_import import seed_canonical_data
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
        "Eligible submitted observations may adjust provisional capacity estimates.",
    ),
    (
        "schedule-non-instrumental-play",
        "Schedule Non-Instrumental Play",
        "This protocol records evidence but is not score-active",
    ),
    (
        "practice-emotional-cue-detection",
        "Practice Emotional Cue Detection",
        "This protocol records evidence but is not score-active",
    ),
    (
        "state-and-maintain-one-boundary",
        "State and Maintain One Boundary",
        "This protocol records evidence but is not score-active",
    ),
    (
        "complete-an-attention-presence-experiment",
        "Complete an Attention-Presence Experiment",
        "This protocol records evidence but is not score-active",
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
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
        f"Page has horizontal overflow at {page.viewport_size}"
    )


def save_walkthrough_screenshot(page, name):
    path = ROOT / "test-results" / "pilot-walkthrough" / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=path, full_page=True)


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
        re.compile(r"completing this practice does not establish mastery"),
    ).wait_for()


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_mobile_keyboard_walkthrough_covers_all_five_protocols(live_server, page: Page):
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
    expect(page.locator(".practice-card")).to_have_count(5)
    assert_no_horizontal_overflow(page)
    save_walkthrough_screenshot(page, "mobile-practice-library")

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
def test_play_protocol_setup_is_specific_and_score_inactive(live_server, page: Page):
    create_browser_user()
    seed_browser_data()
    log_in(live_server, page)

    page.goto(f"{live_server.url}/practices/schedule-non-instrumental-play/")
    page.get_by_role("heading", name="Schedule Non-Instrumental Play").wait_for()
    page.get_by_text("You will not need to invent the practice.").wait_for()
    page.get_by_role("link", name="Start guided setup").click()
    page.get_by_text("will not change your profile or recommendation").wait_for()
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
    page.get_by_role("button", name="I have reviewed the three actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("A specific play window was reserved").wait_for()
    assert page.get_by_label("Expected reciprocity").count() == 0


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
    page.get_by_text("will not change your profile or recommendation").wait_for()
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
    page.get_by_role("button", name="I have reviewed the three actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("I asked a neutral question to check my impression").wait_for()
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
    page.get_by_text("will not change your profile or recommendation").wait_for()
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
    page.get_by_role("button", name="I have reviewed the three actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("I stated the boundary directly in specific words").wait_for()
    page.get_by_label(
        "I followed through proportionately or restated the boundary within seven days"
    ).wait_for()
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
    page.get_by_text("will not change your profile or recommendation").wait_for()
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
    page.get_by_role("button", name="I have reviewed the three actions").click()
    page.get_by_role("button", name="Begin practice").click()
    page.get_by_role("link", name="Add compact check-in").click()
    page.get_by_label("I noticed attention drift and deliberately returned").wait_for()
    page.get_by_label("I compared the usual and changed condition").wait_for()
    page.get_by_label("I repeated the more workable condition within seven days").wait_for()
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
    page.get_by_role("button", name="I have reviewed the three actions").click()
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
    page.get_by_label("The interaction moved beyond transactional content").check()
    page.get_by_label("Personally meaningful information was voluntarily shared").check()
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
    page.get_by_text("This observation has a versioned score disposition.").wait_for()
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
    assert exported["profile_scores_modified"] is True
    assert exported["profile_scores_modified_by_export"] is False
    page.get_by_role("link", name="Read evidence explanation").click()
    page.get_by_role("heading", name="Listen to what matters now").wait_for()
    page.get_by_role("link", name="Profile", exact=True).click()
    page.get_by_role("heading", name="What submitted evidence has changed").wait_for()
    page.get_by_text("Current · versioned").wait_for()
    page.get_by_text(
        re.compile(r"Every transition keeps an immutable before-and-after"),
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

    page.get_by_role("link", name="Review and complete").click()
    page.get_by_text("Completing this practice does not establish mastery.").wait_for()
    page.get_by_label("What did this practice show you?").fill(
        "Specific invitations made the next step clearer."
    )
    page.get_by_role(
        "button",
        name="Submit final review and complete practice",
    ).click()
    page.get_by_role("heading", name="The experiment is closed.").wait_for()
    page.get_by_text("Completing this practice does not establish mastery.").wait_for()
    assert PracticeSprint.objects.get().status == PracticeSprint.Status.COMPLETED
