"""CORS and reverse-proxy identity checks for the Vercel + Render deploy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import parse_cors_origins, settings  # noqa: E402


class CorsOriginParseTests(unittest.TestCase):
    def test_splits_and_strips(self) -> None:
        self.assertEqual(
            parse_cors_origins("https://a.vercel.app, https://b.vercel.app"),
            ("https://a.vercel.app", "https://b.vercel.app"),
        )

    def test_empty_and_whitespace(self) -> None:
        self.assertEqual(parse_cors_origins(""), ())
        self.assertEqual(parse_cors_origins("  ,  , "), ())
        self.assertEqual(
            parse_cors_origins("  http://localhost:5173  "),
            ("http://localhost:5173",),
        )


class CorsHeaderTests(unittest.TestCase):
    def tearDown(self) -> None:
        object.__setattr__(settings, "cors_origin", "http://localhost:5173")
        object.__setattr__(settings, "cors_origin_regex", "")

    def test_allows_listed_origin(self) -> None:
        from app import create_app

        object.__setattr__(
            settings,
            "cors_origin",
            "https://skyeye.vercel.app,http://localhost:5173",
        )
        client = create_app().test_client()
        response = client.get(
            "/api/health",
            headers={"Origin": "https://skyeye.vercel.app"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://skyeye.vercel.app",
        )

    def test_does_not_echo_unknown_origin(self) -> None:
        from app import create_app

        object.__setattr__(settings, "cors_origin", "https://skyeye.vercel.app")
        client = create_app().test_client()
        response = client.get(
            "/api/health",
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://evil.example",
        )

    def test_regex_allows_vercel_preview(self) -> None:
        from app import create_app

        object.__setattr__(settings, "cors_origin_regex", r"https://.*\.vercel\.app")
        client = create_app().test_client()
        preview = "https://skyeye-git-main-user.vercel.app"
        response = client.get("/api/health", headers={"Origin": preview})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), preview)


class TrustProxyTests(unittest.TestCase):
    def tearDown(self) -> None:
        object.__setattr__(settings, "trust_proxy", False)

    def test_untrusted_ignores_forwarded_for(self) -> None:
        from app import create_app
        from ratelimit import client_identity

        object.__setattr__(settings, "trust_proxy", False)
        app = create_app()

        @app.get("/_whoami")
        def whoami() -> str:
            return client_identity()

        response = app.test_client().get(
            "/_whoami",
            headers={"X-Forwarded-For": "203.0.113.9"},
            environ_base={"REMOTE_ADDR": "10.0.0.2"},
        )
        self.assertEqual(response.get_data(as_text=True), "10.0.0.2")

    def test_trusted_uses_proxy_client_hop(self) -> None:
        from app import create_app
        from ratelimit import client_identity

        object.__setattr__(settings, "trust_proxy", True)
        app = create_app()

        @app.get("/_whoami")
        def whoami() -> str:
            return client_identity()

        response = app.test_client().get(
            "/_whoami",
            headers={"X-Forwarded-For": "203.0.113.9"},
            environ_base={"REMOTE_ADDR": "10.0.0.2"},
        )
        self.assertEqual(response.get_data(as_text=True), "203.0.113.9")


if __name__ == "__main__":
    unittest.main()
