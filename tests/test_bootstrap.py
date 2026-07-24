from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command


@pytest.mark.django_db
def test_bootstrap_requires_credentials_for_empty_database(monkeypatch):
    monkeypatch.delenv("APP_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("APP_BOOTSTRAP_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="required"):
        call_command("bootstrap_user")


@pytest.mark.django_db
def test_bootstrap_is_one_time_and_does_not_reset_password(monkeypatch):
    monkeypatch.setenv("APP_BOOTSTRAP_USERNAME", "grounded")
    monkeypatch.setenv("APP_BOOTSTRAP_PASSWORD", "Strong-Bootstrap-Passphrase-2047!")
    output = StringIO()
    call_command("bootstrap_user", stdout=output)

    user = get_user_model().objects.get(username="grounded")
    original_hash = user.password
    assert user.check_password("Strong-Bootstrap-Passphrase-2047!")
    assert not user.is_staff
    assert not user.is_superuser

    monkeypatch.setenv("APP_BOOTSTRAP_PASSWORD", "Different-Password-That-Must-Not-Apply-77!")
    call_command("bootstrap_user", stdout=output)
    user.refresh_from_db()
    assert user.password == original_hash
    assert not user.check_password("Different-Password-That-Must-Not-Apply-77!")
    assert get_user_model().objects.count() == 1
    assert "Bootstrap skipped" in output.getvalue()
