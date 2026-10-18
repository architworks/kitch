"""Bounds on a single agent run, so a tool loop cannot run away.

Every runner.run_async call in Kitch (chat, photo analysis, pantry
reconciliation and the Instamart cart agent) uses these. A nested run, such as
the cart agent started from a chat tool, is its own run with its own budget.
ADK is imported lazily so importing this module stays cheap.
"""

from __future__ import annotations

from typing import Any

# ADK's own default is 500 model calls per run. A normal request uses well
# under 20; the cart agent for a long list uses more, so 100 leaves headroom.
MAX_LLM_CALLS_PER_RUN = 100
RUN_TIMEOUT_SECONDS = 300

RUN_LIMIT_MESSAGE = (
    "That request needed more steps than Kitch allows in one go, so it was stopped. "
    "Some changes may already be saved, so check before trying again with a simpler request."
)


def limited_run_config() -> Any:
    from google.adk.agents.run_config import RunConfig

    return RunConfig(max_llm_calls=MAX_LLM_CALLS_PER_RUN)


def is_run_limit_error(error: BaseException) -> bool:
    """True when a run hit the model-call cap or the time limit."""
    if isinstance(error, TimeoutError):
        return True
    from google.adk.agents.invocation_context import LlmCallsLimitExceededError

    return isinstance(error, LlmCallsLimitExceededError)
