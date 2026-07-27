import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_is_required_for_user_facing_pages(client):
    for url in (
        reverse("growth:home"),
        reverse("growth:profile"),
        reverse("growth:assessment"),
        reverse("growth:practice-list"),
        reverse("growth:evidence-ledger"),
        reverse("growth:evidence-export"),
        reverse("password_change"),
    ):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(f"{reverse('login')}?next=")


@pytest.mark.django_db
def test_health_and_login_are_public(client):
    health = client.get(reverse("health"))
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    login = client.get(reverse("login"))
    assert login.status_code == 200
    assert b"Sign in" in login.content
    assert "csrftoken" in login.cookies


@pytest.mark.django_db
def test_authenticated_home_and_profile_render_pilot_seed(client, user, seeded):
    client.force_login(user)

    home = client.get(reverse("growth:home"))
    assert home.status_code == 200
    assert b"assessment baseline remains fixed" in home.content
    assert b"Deepen One Existing Friendship" in home.content
    assert b"Review and set up" in home.content
    assert b'href="#main-content"' in home.content
    assert b'id="main-content"' in home.content
    assert b'tabindex="-1"' in home.content

    profile = client.get(reverse("growth:profile"))
    assert profile.status_code == 200
    assert b"Raw self-report" in profile.content
    assert b"Calibrated estimate" in profile.content
    assert b"Evidence confidence" in profile.content
    assert b"Current estimate" in profile.content
    assert b"The Seeker" in profile.content
    assert b"Friendship, Belonging, and Hospitality" in profile.content
    assert b"human worth" in profile.content


@pytest.mark.django_db
def test_logout_requires_post(client, user):
    client.force_login(user)
    response = client.get(reverse("logout"))
    assert response.status_code == 405
    response = client.post(reverse("logout"))
    assert response.status_code == 302
