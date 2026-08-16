"""Authorization invariants for agent-driven grocery commerce."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.instamart_cart_agent import INSTAMART_AGENT_MCP_TOOLS  # noqa: E402
from app.commerce_policy import (  # noqa: E402
    CommercePermission,
    CommercePolicyError,
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

    def test_reads_are_allowed_and_unknown_tools_fail_closed(self):
        CommerceToolPolicy.authorize("search_products")
        with self.assertRaises(CommercePolicyError):
            CommerceToolPolicy.authorize("new_mutating_provider_tool")

    def test_cart_write_requires_server_owned_cart_authority(self):
        with self.assertRaises(CommercePolicyError):
            CommerceToolPolicy.authorize("update_cart")
        with commerce_request_context(
            source="chat_sync",
            permissions={CommercePermission.READ, CommercePermission.CART_WRITE},
            operation_id="chat-1",
        ):
            CommerceToolPolicy.authorize("update_cart")

    def test_checkout_is_rejected_from_chat_and_cart_agent(self):
        for source in ("chat_sync", "ui_sync", "ui_order_preflight"):
            with commerce_request_context(
                source=source,
                permissions={
                    CommercePermission.READ,
                    CommercePermission.CART_WRITE,
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


if __name__ == "__main__":
    unittest.main()
