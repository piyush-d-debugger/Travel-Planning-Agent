

import json
import logging
import re
from typing import Optional

from google.genai import types
from google.adk.models import LlmRequest, LlmResponse
from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Shared helpers
# --------------------------------------------------

def _text_response(text: str) -> LlmResponse:
  
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _response_text(llm_response: LlmResponse) -> str:
    if not llm_response.content or not llm_response.content.parts:
        return ""
    return "".join(p.text for p in llm_response.content.parts if p.text)


def _last_user_text(llm_request: LlmRequest) -> str:
    for content in reversed(llm_request.contents or []):
        if content.role == "user":
            return " ".join(p.text for p in (content.parts or []) if p.text)
    return ""


# --------------------------------------------------
#  quota-error handlers (on_model_error_callback)
# --------------------------------------------------

def _is_quota_error(error: Exception) -> bool:
    """True for HTTP 429 / quota exhaustion errors."""
   
    return getattr(error, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(error)


def make_quota_handler(fallback_text: str):
    """Builds an on_model_error_callback that returns fallback_text on quota errors."""

    def handler(
        callback_context: CallbackContext,
        llm_request: LlmRequest,
        error: Exception,
    ) -> LlmResponse | None:
        if not _is_quota_error(error):
            return None  

        agent_name = getattr(callback_context, "agent_name", "unknown agent")
        logger.warning("Quota exhausted in %s: %s", agent_name, error)
        return _text_response(fallback_text)

    return handler


SPECIALIST_FALLBACK = (
    "NO RESULTS: the live search service was unavailable (quota exceeded), "
    "so no options could be fetched. Do not invent any."
)

def router_json(direct_response: str) -> str:
    """JSON text in the full RouterDecision shape, used when the router model is not called.

    Keep this in sync with RouterDecision in agent.py: the schema has no defaults,
    so every field must be present.
    """
    return json.dumps({
        "is_travel_related": False,
        "travel_request": "",
        "skipped_request": "",
        "direct_response": direct_response,
        "origin": "",
        "destination": "",
        "start_date": "",
        "end_date": "",
        "is_round_trip": False,
        "activities": [],
        "estimated_one_way_train_hours": 0,
        "activity_conflicts": "",
    })


ROUTER_FALLBACK = router_json(
    "Due to high traffic, I cannot process your request right now. "
    "Please try again in a few minutes."
)


BUILDER_FALLBACK = (
    "Due to high traffic, I cannot build your itinerary right now. "
    "Please try again in a few minutes."
)

handle_specialist_quota_error = make_quota_handler(SPECIALIST_FALLBACK)
handle_router_quota_error = make_quota_handler(ROUTER_FALLBACK)
handle_builder_quota_error = make_quota_handler(BUILDER_FALLBACK)


handle_quota_error = handle_builder_quota_error


# --------------------------------------------------
#  prompt-injection guardrails
# --------------------------------------------------

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard .{0,40}(instructions|rules)",
    r"(reveal|show|print|repeat).{0,40}(system|hidden|internal) (prompt|instructions)",
    r"forget (your|all|the) (instructions|rules)",
    r"you are no longer",
]


def _looks_like_injection(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in INJECTION_PATTERNS)


def router_input_guard(callback_context, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """before_model_callback for the router.

    Returns a response to skip the model call, or None to let it proceed.
    The router has output_schema=RouterDecision, so the blocking reply MUST be
    valid JSON in that shape.
    """
    text = _last_user_text(llm_request)

    if len(text) > 2000 or _looks_like_injection(text):
        return _text_response(router_json(
            "I can help you find trains, hotels, and activities for your trip. "
            "I cannot assist with that request."
        ))

    return None


MAX_FIELD_CHARS = 1500


def _scrub(value):
    """Recursively clean strings inside a tool result."""
    if isinstance(value, str):
        # Drop any sentence that looks like an instruction aimed at the AI
        sentences = re.split(r"(?<=[.!?])\s+", value)
        kept = [s for s in sentences if not _looks_like_injection(s)]
        return " ".join(kept)[:MAX_FIELD_CHARS]
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    return value


def tool_result_guard(tool, args, tool_context, tool_response):
    """after_tool_callback for the specialists.

    Returning a value replaces the tool's real result with the cleaned one.
    """
    return _scrub(tool_response)


CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def itinerary_output_guard(callback_context, llm_response: LlmResponse) -> Optional[LlmResponse]:
    """after_model_callback for the itinerary builder: removes code blocks."""
    text = _response_text(llm_response)
    if "```" not in text:
        return None
    return _text_response(CODE_FENCE.sub("", text))
