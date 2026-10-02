"""Safe recovery for model-generated tool names that are not registered.

No application tool ran in this case, so returning a tool response lets the
agent reconsider the call without retrying a potentially mutating operation.
All real tool exceptions continue to propagate normally.
"""

from __future__ import annotations

from typing import Any


def recover_unknown_tool_error(
    *, tool: Any, args: dict[str, Any], tool_context: Any, error: Exception
) -> dict[str, Any] | None:
    del args, tool_context
    message = str(error)
    is_unknown_tool = (
        getattr(tool, "description", "") == "Tool not found"
        or ("Tool '" in message and "not found" in message)
    )
    if not is_unknown_tool:
        return None
    return {
        "status": "error",
        "code": "unknown_tool",
        "message": (
            f"{getattr(tool, 'name', 'The requested tool')} is not registered. "
            "Re-read the tools available to you and retry with the exact registered "
            "tool name. Do not claim that any change was saved."
        ),
    }
