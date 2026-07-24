import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page

from growth.services.canonical_import import seed_canonical_data


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_login_home_and_profile_core_flow(live_server, page: Page):
    get_user_model().objects.create_user(
        username="grounded",
        password="Browser-Test-Password-2047!",
    )
    seed_canonical_data()

    page.goto(f"{live_server.url}/")
    assert "/accounts/login/" in page.url
    page.get_by_label("Username").fill("grounded")
    page.get_by_label("Password").fill("Browser-Test-Password-2047!")
    page.get_by_role("button", name="Sign in").click()

    page.wait_for_url(f"{live_server.url}/")
    page.get_by_role("heading", name="No practice in progress").wait_for()
    page.get_by_text("Deepen One Existing Friendship", exact=True).wait_for()
    page.get_by_role("link", name="View developmental profile").click()

    page.wait_for_url(f"{live_server.url}/profile/")
    page.get_by_role("heading", name="A provisional map, not an identity.").wait_for()
    page.get_by_text("The Seeker", exact=True).wait_for()
    page.get_by_text("Completing a practice will not change this profile.").wait_for()
