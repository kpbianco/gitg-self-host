from django.conf import settings
from django.contrib.auth.views import redirect_to_login


class RequireApplicationLoginMiddleware:
    """Require authentication everywhere except login, health, and static assets."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public_paths = {settings.LOGIN_URL, "/health/"}
        is_static = request.path_info.startswith(settings.STATIC_URL)
        if (
            not request.user.is_authenticated
            and request.path_info not in public_paths
            and not is_static
        ):
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        return self.get_response(request)
