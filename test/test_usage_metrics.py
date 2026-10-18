"""Usage metrics record names, timing and token counts, never content."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import usage_metrics  # noqa: E402


def event(author, calls=(), usage=None):
    return SimpleNamespace(
        author=author,
        usage_metadata=usage,
        get_function_calls=lambda: [SimpleNamespace(name=name, args={"query": "secret"}) for name in calls],
    )


class UsageMetricsTests(unittest.TestCase):
    def collect(self, *events, kind="chat"):
        token = usage_metrics.start_usage(kind)
        for item in events:
            usage_metrics.note_agent_event(item)
        return usage_metrics.end_usage(token)

    def test_records_feature_names_tokens_and_model_calls(self):
        tokens = SimpleNamespace(prompt_token_count=120, candidates_token_count=30, thoughts_token_count=5)
        collector = self.collect(
            event("user"),
            event("kitch_coordinator", usage=tokens),
            event("nutrition_tracker", calls=["log_macros_tool"], usage=tokens),
        )
        self.assertEqual(collector.features, {"chat", "nutrition", "log_macros_tool"})
        self.assertEqual((collector.model_calls, collector.input_tokens, collector.output_tokens), (2, 240, 70))
        self.assertIsNotNone(collector.first_response_ms)

    def test_grocery_app_activity_collapses_to_one_generic_feature(self):
        collector = self.collect(
            event("recipe_grocery_planner", calls=["sync_provider_cart_tool", "instamart_conversation_tool"]),
            event("instamart_cart_agent", calls=["search_products", "update_cart"]),
        )
        self.assertEqual(collector.features, {"recipes_and_groceries", "grocery_app"})

    def test_outside_a_request_nothing_is_collected(self):
        usage_metrics.note_agent_event(event("chef_planner"))  # no collector: a no-op

    def test_outcomes_follow_status_unless_a_handler_marked_one(self):
        collector = self.collect()
        self.assertEqual(usage_metrics.usage_row(collector, 200, "u", "h")["outcome"], "ok")
        for status, outcome in ((429, "quota"), (504, "limit"), (422, "rejected"), (500, "error")):
            self.assertEqual(usage_metrics.usage_row(collector, status, "u", "h")["outcome"], outcome)
        token = usage_metrics.start_usage("chat")
        usage_metrics.mark_outcome("limit")
        self.assertEqual(usage_metrics.usage_row(usage_metrics.end_usage(token), 200, "u", "h")["outcome"], "limit")

    def test_pseudonyms_are_keyed_stable_and_not_the_raw_id(self):
        with patch.dict(os.environ, {"KITCH_AUTH_SESSION_SECRET": "a" * 40}):
            first = usage_metrics.pseudonym("account", "google-123")
            self.assertEqual(first, usage_metrics.pseudonym("account", "google-123"))
            self.assertNotEqual(first, usage_metrics.pseudonym("household", "google-123"))
            self.assertNotIn("google-123", first)
        with patch.dict(os.environ, {"KITCH_AUTH_SESSION_SECRET": "b" * 40}):
            self.assertNotEqual(first, usage_metrics.pseudonym("account", "google-123"))
        with patch.dict(os.environ, {"KITCH_AUTH_SESSION_SECRET": ""}):
            self.assertIsNone(usage_metrics.pseudonym("account", "google-123"))


if __name__ == "__main__":
    unittest.main()
