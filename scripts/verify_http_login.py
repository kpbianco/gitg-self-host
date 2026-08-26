#!/usr/bin/env python3
"""Verify public/authenticated HTTP boundaries and a real CSRF-protected login."""

from __future__ import annotations

import argparse
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HTTP_TIMEOUT_SECONDS = 30


class CsrfTokenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        attributes = dict(attrs)
        if attributes.get("name") == "csrfmiddlewaretoken":
            self.token = attributes.get("value")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def normalized_base_url(value: str) -> str:
    return value.rstrip("/")


def assert_health(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/health/", timeout=HTTP_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")
        if response.status != 200 or body != '{"status": "ok"}':
            raise RuntimeError(f"Unexpected health response: {response.status} {body!r}")


def validate_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise RuntimeError(f"Authenticated path must be a local absolute path: {path!r}")
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError(f"Authenticated path must not contain a URL or query: {path!r}")
    decoded_segments = urllib.parse.unquote(parsed.path).split("/")
    if any(segment in {".", ".."} for segment in decoded_segments):
        raise RuntimeError(f"Authenticated path must not contain traversal: {path!r}")
    return path


def assert_anonymous_redirect(base_url: str, path: str = "/") -> None:
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        opener.open(f"{base_url}{path}", timeout=HTTP_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location", "")
        expected_location = f"/accounts/login/?next={urllib.parse.quote(path, safe='/')}"
        if exc.code != 302 or location != expected_location:
            raise RuntimeError(
                f"Unexpected anonymous response: {exc.code} Location={location!r}"
            ) from exc
        return
    raise RuntimeError(f"Anonymous access to authenticated path {path!r} was not redirected.")


def login(base_url: str, username: str, password: str) -> tuple[str, str, http.cookiejar.CookieJar]:
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    login_url = f"{base_url}/accounts/login/?next=/"

    with opener.open(login_url, timeout=HTTP_TIMEOUT_SECONDS) as response:
        parser = CsrfTokenParser()
        parser.feed(response.read().decode("utf-8"))
    if not parser.token:
        raise RuntimeError("The login page did not provide a CSRF token.")

    encoded = urllib.parse.urlencode(
        {
            "csrfmiddlewaretoken": parser.token,
            "username": username,
            "password": password,
            "next": "/",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        login_url,
        data=encoded,
        headers={"Referer": login_url},
        method="POST",
    )
    with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.geturl(), response.read().decode("utf-8"), cookies


def assert_login(
    base_url: str,
    username: str,
    password: str,
    *,
    expect_success: bool,
    authenticated_paths: tuple[str, ...] = (),
) -> None:
    final_url, body, cookies = login(base_url, username, password)
    if expect_success:
        if normalized_base_url(final_url) != base_url or "Welcome back." not in body:
            raise RuntimeError(f"Login did not reach the authenticated home page: {final_url}")
        session_cookies = [cookie for cookie in cookies if cookie.name == "sessionid"]
        if len(session_cookies) != 1:
            raise RuntimeError("Successful login did not establish exactly one session cookie.")
        if not session_cookies[0].has_nonstandard_attr("HttpOnly"):
            raise RuntimeError("The session cookie was not marked HttpOnly.")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
        for path in authenticated_paths:
            with opener.open(f"{base_url}{path}", timeout=HTTP_TIMEOUT_SECONDS) as response:
                response.read()
                if response.status != 200 or urllib.parse.urlsplit(response.geturl()).path != path:
                    raise RuntimeError(
                        f"Authenticated path did not return its expected page: {path!r}"
                    )
        return

    stayed_on_login = "/accounts/login/" in final_url
    showed_error = "That username and password did not match." in body
    if not stayed_on_login or not showed_error:
        raise RuntimeError("Credentials expected to fail were accepted or failed unexpectedly.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--expect",
        choices=("success", "failure"),
        default="success",
    )
    parser.add_argument(
        "--skip-public-boundary",
        action="store_true",
        help="Skip health and anonymous redirect checks on repeated login probes.",
    )
    parser.add_argument(
        "--authenticated-path",
        action="append",
        default=[],
        help="Additional local path that must redirect anonymously and return 200 after login.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = normalized_base_url(args.base_url)
    authenticated_paths = tuple(validate_path(path) for path in args.authenticated_path)
    if not args.skip_public_boundary:
        assert_health(base_url)
        assert_anonymous_redirect(base_url)
        for path in authenticated_paths:
            assert_anonymous_redirect(base_url, path)
    assert_login(
        base_url,
        args.username,
        args.password,
        expect_success=args.expect == "success",
        authenticated_paths=(authenticated_paths if args.expect == "success" else ()),
    )
    print(f"HTTP verification passed ({args.expect} login expected).")


if __name__ == "__main__":
    main()
