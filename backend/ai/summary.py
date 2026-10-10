"""
Ticket titles and descriptions from a chat conversation.

Chats often start with "hi" or end with "thanks, still broken", so the first
user message is a poor ticket title. This picks the messages that actually
describe the problem (using the trained intent model plus the greeting
rules) and builds a short title and a description from them.
"""

import re
from typing import List, Optional, Sequence

from ai.deflector import _has_it_problem, _is_greeting_only
from ai.intent_model import intent_model

TITLE_MAX = 80

# Conversation filler: greetings, confirmations, "still broken", "get me a person"
_FILLER_INTENTS = {"greeting", "vague", "resolved", "not_fixed", "human"}
_FILLER_CONFIDENCE = 0.5

_GREETING_PREFIX = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|helo|yo|good\s+(morning|afternoon|evening|day)|greetings)"
    r"(\s+(there|team|all|everyone|support|it))?[\s,!.:;\-–—]*",
    re.IGNORECASE,
)


def is_substantive(text: str) -> bool:
    """True if the message describes a problem or request, not chat filler."""
    text = (text or "").strip()
    if not text or _is_greeting_only(text):
        return False
    if _has_it_problem(text):
        return True
    label, confidence = intent_model().predict(text)
    return not (label in _FILLER_INTENTS and confidence >= _FILLER_CONFIDENCE)


def _clean(text: str) -> str:
    text = _GREETING_PREFIX.sub("", text.strip())  # "Hi, my vpn..." -> "my vpn..."
    return re.sub(r"\s+", " ", text).strip(" .,!-–—")


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-–—") + "…"


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text)[0]


def problem_messages(user_messages: Sequence[str]) -> List[str]:
    return [m.strip() for m in user_messages if is_substantive(m)]


def summarize_title(user_messages: Sequence[str], fallback: str) -> str:
    """Short ticket title from the messages that describe the problem."""
    problems = [_clean(m) for m in problem_messages(user_messages)]
    problems = [p for p in problems if p]
    if not problems:
        return fallback
    title = _first_sentence(problems[0])
    # A very short first description ("laptop broken") gains the next detail
    if len(title) < 30 and len(problems) > 1:
        title = f"{title} — {_first_sentence(problems[1])}"
    title = _shorten(title, TITLE_MAX)
    return title[0].upper() + title[1:]


def summarize_description(user_messages: Sequence[str]) -> Optional[str]:
    """Everything the user said about the problem, one message per line."""
    problems = problem_messages(user_messages)
    return "\n".join(problems) if problems else None


def is_good_title(title: Optional[str]) -> bool:
    """Reject titles that are just a greeting or filler (e.g. a client sent "Hi")."""
    return bool(title and title.strip() and is_substantive(title))
