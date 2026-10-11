"""Authorization invariants for agent-driven grocery commerce."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.instamart_cart_agent import (  # noqa: E402
    INSTAMART_AGENT_MCP_TOOLS,
    INSTAMART_CONVERSATION_MAX_TOOL_CALLS,
    INSTAMART_CONVERSATION_MCP_TOOLS,
    _after_instamart_tool,
    _before_instamart_conversation_tool,
    _before_instamart_tool,
)
from app.commerce_policy import (  # noqa: E402
    CommercePermission,
    CommercePolicyError,
    CommerceRunCapture,
    CommerceToolPolicy,
    commerce_request_context,
)


class CommerceToolPolicyTests(unittest.TestCase):
    def test_agent_toolset_contains_cart_tools_but_never_checkout(self):
        self.assertEqual(set(INSTAMART_AGENT_MCP_TOOLS), {
            "get_addresses",
            "search_products",
            "your_go_to_items",
            "update_cart",
            "get_cart",
        })
        self.assertNotIn("checkout", INSTAMART_AGENT_MCP_TOOLS)
        self.assertNotIn("clear_cart", INSTAMART_AGENT_MCP_TOOLS)

    def test_conversation_toolset_has_safe_operations_but_never_checkout(self):
        self.assertIn("clear_cart", INSTAMART_CONVERSATION_MCP_TOOLS)
        self.assertIn("apply_coupon", INSTAMART_CONVERSATION_MCP_TOOLS)
        self.assertIn("get_delivery_status", INSTAMART_CONVERSATION_MCP_TOOLS)
        self.assertNotIn("checkout", INSTAMART_CONVERSATION_MCP_TOOLS)
        self.assertNotIn("confirm_order", INSTAMART_CONVERSATION_MCP_TOOLS)

    def test_conversation_allows_multiple_cart_updates(self):
        capture = CommerceRunCapture(
            user_instruction="Remove rice from my Swiggy Instamart cart."
        )
        tool = SimpleNamespace(name="update_cart")
        with commerce_request_context(
            source="chat_instamart",
            permissions={CommercePermission.READ},
            operation_id="multiple-cart-updates",
            capture=capture,
        ):
            _before_instamart_conversation_tool(
                tool=tool,
                args={"items": []},
                tool_context=object(),
                capture=capture,
            )
            _before_instamart_conversation_tool(
                tool=tool,
                args={"items": []},
                tool_context=object(),
                capture=capture,
            )

        self.assertEqual(len(capture.tool_arguments["update_cart"]), 2)

    def test_conversation_tool_call_limit_is_fifty(self):
        capture = CommerceRunCapture(
            user_instruction="Show my Swiggy Instamart cart.",
            tool_arguments={"get_cart": [{}] * (INSTAMART_CONVERSATION_MAX_TOOL_CALLS - 1)},
        )
        tool = SimpleNamespace(name="get_cart")
        with commerce_request_context(
            source="chat_instamart",
            permissions={CommercePermission.READ},
            operation_id="tool-call-limit",
            capture=capture,
        ):
            _before_instamart_conversation_tool(
                tool=tool,
                args={},
                tool_context=object(),
                capture=capture,
            )
            with self.assertRaises(CommercePolicyError):
                _before_instamart_conversation_tool(
                    tool=tool,
                    args={},
                    tool_context=object(),
                    capture=capture,
                )


    def test_reads_are_allowed_and_unknown_tools_fail_closed(self):
        CommerceToolPolicy.authorize("search_products")
        with self.assertRaises(CommercePolicyError):
            CommerceToolPolicy.authorize("new_mutating_provider_tool")

    def test_allowlisted_cart_operations_do_not_require_request_authority(self):
        for tool_name in ("update_cart", "clear_cart", "apply_coupon"):
            CommerceToolPolicy.authorize(tool_name)

    def test_instamart_memory_tools_require_commerce_run_authority(self):
        for tool_name in (
            "search_household_memory_tool",
            "update_household_memory_tool",
        ):
            with self.assertRaises(CommercePolicyError):
                CommerceToolPolicy.authorize(tool_name)
            with commerce_request_context(
                source="ui_sync",
                permissions={CommercePermission.READ},
                operation_id=f"{tool_name}-1",
            ):
                CommerceToolPolicy.authorize(tool_name)

    def test_checkout_is_rejected_from_chat_and_cart_agent(self):
        for source in ("chat_sync", "ui_sync", "ui_order_preflight"):
            with commerce_request_context(
                source=source,
                permissions={
                    CommercePermission.READ,
                    CommercePermission.CHECKOUT,
                },
                operation_id=source,
            ):
                with self.assertRaises(CommercePolicyError):
                    CommerceToolPolicy.authorize("checkout")

    def test_checkout_is_allowed_only_for_ui_place_order(self):
        with commerce_request_context(
            source="ui_place_order",
            permissions={CommercePermission.READ, CommercePermission.CHECKOUT},
            operation_id="order-1",
        ):
            CommerceToolPolicy.authorize("checkout")

    def test_adk_keyword_callback_contract_records_authorized_tool_calls(self):
        capture = CommerceRunCapture()
        tool = SimpleNamespace(name="search_products")
        with commerce_request_context(
            source="ui_sync",
            permissions={CommercePermission.READ},
            operation_id="sync-1",
            capture=capture,
        ):
            _before_instamart_tool(
                tool=tool,
                args={"addressId": "home-1", "query": "eggs"},
                tool_context=object(),
                capture=capture,
                selected_address_id="home-1",
            )
            _after_instamart_tool(
                tool=tool,
                args={"addressId": "home-1", "query": "eggs"},
                tool_context=object(),
                tool_response={"success": True},
                capture=capture,
            )
        self.assertEqual(capture.tool_arguments["search_products"][0]["query"], "eggs")
        self.assertEqual(capture.latest("search_products"), {"success": True})


if __name__ == "__main__":
    unittest.main()
