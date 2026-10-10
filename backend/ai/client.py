"""
Shared Claude client for the three AI jobs.

Every job has a deterministic rule-based fallback, so any failure here
(no key, network error, refusal, malformed output) returns None and the
caller falls back instead of raising.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

from config import settings

if TYPE_CHECKING:
    import anthropic

# The Anthropic SDK is imported only when paid AI is switched on — it takes
# several seconds to load, and in the default free setup it is never used.

logger = logging.getLogger("relaydesk.ai")

Effort = Literal["low", "medium", "high", "xhigh", "max"]

# Server-side refusal fallback: if a safety classifier declines a request,
# the API re-runs it on Anthropic's recommended fallback model in the same call.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def ai_enabled() -> bool:
    """True only when paid AI has been deliberately switched on.

    The Claude API is billed per request. This project runs strictly free:
    ENABLE_PAID_AI defaults to False, and while it is False no request is
    ever sent — even if a real ANTHROPIC_API_KEY is present — and every AI
    job uses the free built-in engine instead."""
    if not settings.ENABLE_PAID_AI:
        return False
    key = settings.ANTHROPIC_API_KEY
    return bool(key) and not key.startswith("sk-ant-your-key") and "dummy" not in key and len(key) >= 20


@lru_cache(maxsize=1)
def get_client() -> anthropic.AsyncAnthropic:
    # Second guard: never even build a client while paid AI is off
    if not ai_enabled():
        raise RuntimeError("Paid AI is disabled (ENABLE_PAID_AI=false)")
    import anthropic
    return anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=settings.AI_TIMEOUT_SECONDS,
        max_retries=2,
    )


async def _create(
    system: str,
    user_content: Union[str, List[Dict[str, Any]]],
    max_tokens: int,
    effort: Effort,
    job: str,
    schema: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """One Messages API call. Returns the reply text, or None on any failure.

    user_content is either a single user prompt or a full multi-turn
    messages list. Thinking is always on for current models and counts
    toward max_tokens, so callers size max_tokens for thinking plus the reply."""
    if not ai_enabled():
        return None
    import anthropic

    messages = [{"role": "user", "content": user_content}] if isinstance(user_content, str) else user_content

    output_config: Dict[str, Any] = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    extra: Dict[str, Any] = {}
    if settings.AI_REFUSAL_FALLBACK:
        extra = {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

    try:
        message = await get_client().beta.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_config=output_config,
            **extra,
        )
    except anthropic.RateLimitError:
        logger.warning("Claude %s call rate-limited; using fallback", job)
        return None
    except anthropic.APIStatusError as e:
        logger.warning("Claude %s call failed with HTTP %s; using fallback", job, e.status_code)
        return None
    except anthropic.APIConnectionError:
        logger.warning("Claude %s call could not connect; using fallback", job)
        return None

    if message.stop_reason == "refusal":
        category = getattr(getattr(message, "stop_details", None), "category", None)
        logger.warning("Claude declined the %s request (category=%s); using fallback", job, category)
        return None
    if message.stop_reason == "max_tokens":
        logger.warning("Claude %s response hit max_tokens=%s; using fallback", job, max_tokens)
        return None

    # Read by block type: responses may start with (empty) thinking blocks
    text = "".join(block.text for block in message.content if block.type == "text").strip()
    return text or None


async def complete_text(system: str, user_content: str, max_tokens: int, job: str, effort: Effort = "low") -> Optional[str]:
    return await _create(system, user_content, max_tokens, effort, job)


def extract_json_object(raw: str) -> Optional[dict]:
    """Parse the first JSON object in a model reply. Structured outputs make
    the reply valid JSON already; this stays tolerant of fences or preamble
    in case a model without structured-output support is configured."""
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass
    start = raw.find("{")
    while start != -1:
        try:
            parsed, _ = json.JSONDecoder().raw_decode(raw[start:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = raw.find("{", start + 1)
    return None


async def complete_json(
    system: str,
    user_content: Union[str, List[Dict[str, Any]]],
    max_tokens: int,
    job: str,
    schema: Dict[str, Any],
    effort: Effort = "medium",
) -> Optional[dict]:
    raw = await _create(system, user_content, max_tokens, effort, job, schema=schema)
    if raw is None:
        return None
    data = extract_json_object(raw)
    if data is None:
        logger.warning("Claude %s reply was not valid JSON; using fallback", job)
    return data
