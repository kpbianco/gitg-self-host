import os

# pytest-playwright owns an event loop while pytest-django creates the live test
# database. This flag is scoped to E2E collection; application code remains sync.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
