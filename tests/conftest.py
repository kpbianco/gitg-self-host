import os

import pytest
from django.contrib.auth import get_user_model

from growth.services.canonical_import import seed_canonical_data


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="kian",
        password="local-test-password-47!",
    )


@pytest.fixture
def seeded(user):
    return seed_canonical_data()


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    launch_args = dict(browser_type_launch_args)
    executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if executable:
        launch_args["executable_path"] = executable
        launch_args["args"] = [*launch_args.get("args", []), "--no-sandbox"]
    return launch_args
