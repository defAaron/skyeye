"""Rate-limiter unit + Flask contract checks. No provider keys required."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from extract.providers import ExtractProviderError, extract_report  # noqa: E402
from ratelimit import RateLimiter, limiter  # noqa: E402


class SlidingWindowTests(unittest.TestCase):
    def test_allows_up_to_limit_then_blocks(self) -> None:
        window = RateLimiter()
        self.assertTrue(window.consume("k", [(2, 60.0)])[0])
        self.assertTrue(window.consume("k", [(2, 60.0)])[0])
        allowed, retry = window.consume("k", [(2, 60.0)])
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)

    def test_rpm_and_rpd_are_all_or_nothing(self) -> None:
        window = RateLimiter()
        self.assertTrue(window.consume("gemini", [(2, 60.0), (2, 86_400.0)])[0])
        self.assertTrue(window.consume("gemini", [(2, 60.0), (2, 86_400.0)])[0])
        allowed, _retry = window.consume("gemini", [(2, 60.0), (2, 86_400.0)])
        self.assertFalse(allowed)
        # A rejected consume must not take a later slot after reset of one window.
        self.assertFalse(window.consume("gemini", [(2, 60.0), (2, 86_400.0)])[0])

    def test_cooldown_blocks_even_with_budget(self) -> None:
        window = RateLimiter()
        self.assertTrue(window.consume("gemini", [(8, 60.0)])[0])
        window.trip_cooldown("gemini", 30)
        allowed, retry = window.consume("gemini", [(8, 60.0)])
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)

    def test_separate_keys_do_not_share_budget(self) -> None:
        window = RateLimiter()
        self.assertTrue(window.consume("gemini", [(1, 60.0)])[0])
        self.assertTrue(window.consume("groq", [(1, 60.0)])[0])
        self.assertFalse(window.consume("gemini", [(1, 60.0)])[0])
        self.assertFalse(window.consume("groq", [(1, 60.0)])[0])

    def test_non_positive_limit_is_not_enforced(self) -> None:
        window = RateLimiter()
        for _ in range(5):
            self.assertTrue(window.consume("open", [(0, 60.0)])[0])


class GeminiFallbackTests(unittest.TestCase):
    def test_local_gemini_limit_falls_back_to_groq(self) -> None:
        from unittest.mock import patch

        groq_payload = {
            "location_text": "Bruce Trail, Milton",
            "time_last_seen": "15:00",
            "elapsed_hours": 4.5,
            "subject": {
                "age": 70,
                "clothing": "red jacket",
                "distinguishing_features": None,
                "category": "elderly_hiker",
            },
            "terrain_hint": "wooded trail",
            "provider": "groq",
            "disclaimer": "test",
        }
        with (
            patch("extract.providers.settings") as mock_settings,
            patch("extract.providers.acquire_gemini", return_value=(False, 12)),
            patch("extract.providers._post_json") as post,
            patch("extract.providers._groq", return_value=groq_payload) as groq,
        ):
            mock_settings.gemini_configured = True
            mock_settings.groq_configured = True
            mock_settings.extract_configured = True
            result = extract_report("dad missing near Bruce Trail, Milton")
        self.assertEqual(result["provider"], "groq")
        post.assert_not_called()
        groq.assert_called_once()

    def test_gemini_and_groq_local_limits_return_rate_limited(self) -> None:
        from unittest.mock import patch

        with (
            patch("extract.providers.settings") as mock_settings,
            patch("extract.providers.acquire_gemini", return_value=(False, 12)),
            patch("extract.providers.acquire_groq", return_value=(False, 9)),
            patch("extract.providers._post_json") as post,
        ):
            mock_settings.gemini_configured = True
            mock_settings.groq_configured = True
            mock_settings.extract_configured = True
            with self.assertRaises(ExtractProviderError) as caught:
                extract_report("dad missing near Bruce Trail, Milton")
        self.assertEqual(caught.exception.code, "RATE_LIMITED")
        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(caught.exception.retry_after, 9)
        post.assert_not_called()


class ExtractRateLimitHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import create_app

        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self) -> None:
        limiter.reset()
        self._original = settings.extract_ip_per_minute
        object.__setattr__(settings, "extract_ip_per_minute", 1)

    def tearDown(self) -> None:
        object.__setattr__(settings, "extract_ip_per_minute", self._original)
        limiter.reset()

    def test_second_extract_is_429_without_calling_providers(self) -> None:
        # Empty body still consumes the per-IP slot, and never reaches Gemini/Groq.
        first = self.client.post("/api/extract", json={})
        self.assertEqual(first.status_code, 400)
        self.assertEqual(first.get_json()["error"]["code"], "EMPTY_REPORT")
        second = self.client.post("/api/extract", json={})
        self.assertEqual(second.status_code, 429)
        body = second.get_json()
        self.assertEqual(body["error"]["code"], "RATE_LIMITED")
        self.assertNotIn("aiza", second.get_data(as_text=True).lower())
        self.assertNotIn("gsk_", second.get_data(as_text=True).lower())
        retry_after = second.headers.get("Retry-After")
        self.assertIsNotNone(retry_after)
        self.assertGreaterEqual(int(retry_after), 1)


if __name__ == "__main__":
    unittest.main()
