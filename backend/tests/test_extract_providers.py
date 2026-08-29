"""Extract provider ids and Groq payload parsing. No live keys required."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from extract.providers import GROQ_MODELS, _choice_text, _parse_json_text  # noqa: E402


class GroqModelIdTests(unittest.TestCase):
    def test_retired_llama_ids_are_not_used(self) -> None:
        retired = {"llama-3.1-8b-instant", "llama-3.3-70b-versatile"}
        self.assertTrue(retired.isdisjoint(GROQ_MODELS))

    def test_gpt_oss_is_primary_fallback(self) -> None:
        self.assertEqual(GROQ_MODELS[0], "openai/gpt-oss-20b")
        self.assertIn("openai/gpt-oss-120b", GROQ_MODELS)


class ChoiceTextTests(unittest.TestCase):
    def test_string_content(self) -> None:
        payload = {"choices": [{"message": {"content": '{"location_text":"x"}'}}]}
        self.assertEqual(_choice_text(payload), '{"location_text":"x"}')

    def test_array_of_parts(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": '{"location_text":'},
                            {"type": "text", "text": '"Bruce Trail"}'},
                        ]
                    }
                }
            ]
        }
        parsed = _parse_json_text(_choice_text(payload))
        self.assertEqual(parsed, {"location_text": "Bruce Trail"})

    def test_empty_content_raises(self) -> None:
        payload = {"choices": [{"message": {"content": ""}}]}
        with self.assertRaises(TypeError):
            _choice_text(payload)


if __name__ == "__main__":
    unittest.main()
