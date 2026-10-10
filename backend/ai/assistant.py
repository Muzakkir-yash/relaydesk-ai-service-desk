"""
The self-service support chatbot (first line of support).

A user chats with the assistant first. It asks clarifying questions, walks
the user through fixes grounded in the company knowledge base, and decides
when the conversation should end — either the user confirms the fix
("resolved") or the issue needs a person ("escalate"), at which point the
ticket goes to a technician with a handover briefing.

With an Anthropic API key the conversation is run by Claude; without one a
rule-based engine (ai/deflector.py) handles it using the same knowledge.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from ai.classifier import _fallback_classify
from ai.client import ai_enabled, complete_json
from ai.deflector import diagnose_and_triage, _has_it_problem
from ai.intent_model import category_model, intent_model
from ai.knowledge import KnowledgeIndex, conversation_query
from ai.summary import is_good_title, summarize_title

logger = logging.getLogger("relaydesk.assistant")

INTENTS = ["greeting", "clarify", "troubleshoot", "resolved", "escalate"]
CATEGORIES = ["hardware", "software", "network", "access", "account", "general", "other"]
PRIORITIES = ["low", "medium", "high", "critical"]

SYSTEM_PROMPT = """\
You are the first-line IT support assistant for a company's internal service desk. Employees chat
with you before a human technician gets involved. Your job is to solve what can safely be solved
through self-service, and to hand everything else to a technician quickly and cleanly.

How to run the conversation:
- Greeting or small talk with no problem described: greet briefly and ask what's going wrong.
- Problem too vague to act on: ask ONE focused question that most narrows it down (which device or
  app, the exact error text, when it started, whether others are affected). Don't ask several at once.
- Clear problem that a user can fix themselves: give a short numbered list of concrete steps, most
  likely fix first, with exact menu paths or commands. End by asking them to say whether it worked.
- If a step didn't work, use what they told you: try the next most likely cause rather than
  repeating yourself.
- Match the user's language and tone. Keep replies short; this is a chat, not a manual.

Company knowledge:
- Each user turn may include <knowledge> articles from the company knowledge base. When one fits,
  base your steps on it — it reflects how this company's systems are set up — and list its id in
  used_article_ids. Ignore articles that don't fit the problem.
- Never invent company-specific details (portal URLs, server names, phone numbers, policies) that
  aren't in the knowledge provided. Give generic steps instead.

When the conversation ends:
- intent "resolved": only after the user has clearly confirmed the problem is fixed. Thank them briefly.
- intent "escalate": when the user asks for a person; when the fix needs admin rights, a password or
  access change, physical repair, a purchase or approval; when two different approaches have failed;
  for suspected security incidents (phishing, malware, a compromised account) — escalate those
  immediately with priority high or critical; or when many people are affected. Tell the user a
  technician will pick it up with the full conversation, so they won't need to repeat anything.
- Otherwise intent is "greeting", "clarify" or "troubleshoot" to match what you did.

Also fill in: subject (a short ticket title for the problem, empty if none has been described yet),
category, and priority (critical = many users or business stopped; high = one person fully blocked;
medium = degraded but working; low = question or minor).
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "intent": {"type": "string", "enum": INTENTS},
        "subject": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": PRIORITIES},
        "used_article_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["reply", "intent", "subject", "category", "priority", "used_article_ids"],
    "additionalProperties": False,
}


def _knowledge_block(hits) -> str:
    if not hits:
        return "<knowledge>No matching knowledge-base articles.</knowledge>"
    parts = [f'<article id="{h.article["id"]}" title="{h.article["title"]}">\n{h.article["body"][:2500]}\n</article>'
             for h in hits]
    return "<knowledge>\n" + "\n".join(parts) + "\n</knowledge>"


def build_messages(message: str, history: Sequence[Dict], knowledge: str) -> List[Dict[str, Any]]:
    """Turn the chat widget's history into alternating user/assistant turns.
    The retrieved knowledge rides on the newest user turn only, so earlier
    turns stay byte-identical between requests."""
    turns: List[Dict[str, Any]] = []
    for m in history:
        text = str(m.get("text") or m.get("body") or "").strip()
        if not text:
            continue
        is_user = m.get("sender") == "user" or m.get("sender_type") in ("user", "enduser")
        role = "user" if is_user else "assistant"
        if not turns and role == "assistant":
            continue  # the conversation must start with the user
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + text
        else:
            turns.append({"role": role, "content": text})

    # The widget appends the newest message to history before sending; make
    # sure it is the final user turn exactly once.
    if not turns or turns[-1]["role"] != "user":
        turns.append({"role": "user", "content": message})
    elif not turns[-1]["content"].endswith(message):
        turns[-1]["content"] += "\n\n" + message

    turns[-1]["content"] = f"{knowledge}\n\n{turns[-1]['content']}"
    return turns


def _has_assistant_turn(history: Sequence[Dict]) -> bool:
    return any(m.get("sender") in ("ai", "bot", "assistant") or m.get("sender_type") == "ai" for m in history)


async def _claude_turn(message: str, history: Sequence[Dict], hits) -> Optional[Dict[str, Any]]:
    result = await complete_json(
        SYSTEM_PROMPT,
        build_messages(message, history, _knowledge_block(hits)),
        max_tokens=4096,
        job="assistant",
        schema=OUTPUT_SCHEMA,
        effort="low",
    )
    if not result or not str(result.get("reply", "")).strip():
        return None

    intent = result.get("intent") if result.get("intent") in INTENTS else "troubleshoot"
    # The user can't confirm a fix before the assistant has suggested anything
    if intent == "resolved" and not _has_assistant_turn(history):
        intent = "clarify"

    by_id = {h.article["id"]: h.article for h in hits}
    used = [by_id[i] for i in (result.get("used_article_ids") or []) if i in by_id]
    return {
        "reply": result["reply"].strip(),
        "status_intent": intent,
        "subject": str(result.get("subject") or "")[:256],
        "category": result.get("category") if result.get("category") in CATEGORIES else "other",
        "priority": result.get("priority") if result.get("priority") in PRIORITIES else "medium",
        "can_resolve": intent in ("troubleshoot", "resolved"),
        "used_articles": used,
    }


# Below this confidence the trained model defers to the hand-written rules
MODEL_MIN_CONFIDENCE = 0.5
# The category model replaces the keyword rules' category above this confidence
CATEGORY_OVERRIDE_CONFIDENCE = 0.7
INFO_QUESTION_WORDS = {"what", "who", "whom", "whose", "why", "when", "where", "which", "how"}

_ESCALATION_REPLIES = {
    "security": (
        "⚠️ This could be a security incident, so I'm escalating it to our IT security team right away.\n\n"
        "Until they contact you: **don't click anything else** in that message, and if you entered your password "
        "anywhere, **change it now from a device you trust**. If you think something was installed, disconnect "
        "from the network. A technician will contact you shortly."
    ),
    "outage": (
        "Thanks for reporting this. Since it affects more than just you, it's likely a wider outage — I'm escalating "
        "it to the IT team as urgent. You don't need to troubleshoot your own device for this."
    ),
    "human": (
        "Of course — I'm connecting you with a technician now. They'll get our whole conversation, "
        "so you won't need to repeat anything."
    ),
    "request": (
        "This needs a technician rather than self-service steps (new equipment, an install, access, or a repair). "
        "I'm passing it to the IT team now with everything you've told me."
    ),
    "not_fixed": (
        "Sorry that didn't fix it. I'm handing this over to a technician now — they'll see everything we've "
        "already tried, so you won't need to repeat it."
    ),
}
_ESCALATION_PRIORITY = {"security": "high", "outage": "critical"}


def _model_category(text: str) -> str:
    label, confidence = category_model().predict(text)
    if confidence >= MODEL_MIN_CONFIDENCE:
        return label
    return _fallback_classify(text, text)["category"]


def _model_route(message: str, history: Sequence[Dict], hits=()) -> Optional[Dict[str, Any]]:
    """Let the trained intent model handle turns it is confident about.
    Returns None for ordinary problem descriptions (the rule engine and
    knowledge base answer those) or when the model is unsure."""
    intent, confidence = intent_model().predict(message)
    if confidence < MODEL_MIN_CONFIDENCE:
        return None
    # "What does a technician do?" asks for information; "Could someone call me?" is a request
    first_word = (message.strip().lower().split() or [""])[0]
    if intent == "human" and first_word in INFO_QUESTION_WORDS:
        return None
    ai_has_spoken = _has_assistant_turn(history)
    context = conversation_query(message, history)
    base = {"subject": "", "used_articles": [], "can_resolve": False}

    if intent in ("security", "outage", "human", "request") or (intent == "not_fixed" and ai_has_spoken):
        rules = _fallback_classify(context, context)
        priority = _ESCALATION_PRIORITY.get(intent) or (rules["priority"] if rules["priority"] != "low" else "medium")
        return {**base, "reply": _ESCALATION_REPLIES[intent], "status_intent": "escalate",
                "category": "access" if intent == "security" else _model_category(context),
                "priority": priority, "subject": context.strip()[:75]}
    if intent == "info_question":
        # Policy / "how does IT work" questions: answer from the KB, never raise an alarm
        if hits and hits[0].score >= 4.0:
            art = hits[0].article
            reply = (f"Here's what our knowledge base says — **{art['title']}**:\n\n{art['body']}\n\n"
                     "If that doesn't answer your question, I can pass it to the IT team.")
            return {**base, "status_intent": "troubleshoot", "can_resolve": True, "used_articles": [art],
                    "category": "other", "priority": "low", "reply": reply}
        return {**base, "status_intent": "clarify", "category": "other", "priority": "low",
                "reply": ("Good question — I don't have a knowledge-base article on that yet. You can check the IT "
                          "policies page on the intranet, or I can pass your question to the IT team. "
                          "Would you like me to do that?")}
    if intent == "resolved" and ai_has_spoken:
        return {**base, "status_intent": "resolved", "can_resolve": True, "category": "general", "priority": "low",
                "subject": "Self-Service IT Resolution",
                "reply": "🎉 Great — glad that sorted it! I'll close this as resolved. Have a good day!"}
    # Greetings and vague messages only if no concrete IT problem is mentioned
    if intent in ("greeting", "vague") and not _has_it_problem(message):
        if intent == "greeting":
            return {**base, "status_intent": "greeting", "category": "", "priority": "",
                    "reply": "Hi! 👋 How can I help? Tell me what's going wrong — which app or device, and any error you see."}
        return {**base, "status_intent": "clarify", "category": "other", "priority": "low",
                "reply": ("I can help with that — could you tell me a bit more? Which device or app is affected, "
                          "what exactly happens (any error message?), and when did it start?")}
    return None


STRONG_MATCH_SCORE = 4.0  # any category
CATEGORY_MATCH_SCORE = 1.0  # same category as the model's prediction


def _pick_article(hits, category: Optional[str], relaxed: bool) -> Optional[Dict[str, Any]]:
    for hit in hits:
        if hit.score >= STRONG_MATCH_SCORE:
            return hit.article
    if relaxed and category:
        for hit in hits:
            if hit.score >= CATEGORY_MATCH_SCORE and (hit.article.get("category") or "").lower() == category:
                return hit.article
    return None


async def _offline_turn(message: str, history: Sequence[Dict], articles: List[Dict], hits) -> Dict[str, Any]:
    routed = _model_route(message, history, hits)
    if routed:
        return routed
    result = await diagnose_and_triage(message=message, chat_history=list(history), kb_articles=articles)
    if result.get("status_intent") in ("troubleshoot", "clarify"):
        # The trained category model beats the keyword guess when it is confident
        # ("file is locked for editing" is software, not access)
        label, confidence = category_model().predict(conversation_query(message, history))
        if confidence >= CATEGORY_OVERRIDE_CONFIDENCE or result.get("category") in ("other", "general", None, ""):
            result["category"] = label if confidence >= MODEL_MIN_CONFIDENCE else _model_category(conversation_query(message, history))
    # The rule engine only knows its hand-written topics. If it fell back to
    # generic steps or a clarifying question but the knowledge base has a good
    # match (for example an article learned from a technician's fix), answer
    # from that article.
    if result.get("status_intent") in ("troubleshoot", "clarify") and not result.get("used_articles"):
        # When the trained model is confident this is a real problem, the rules
        # merely didn't recognise the wording ("internet is patchy") — accept a
        # weaker match as long as it is in the category the model identified.
        intent, intent_confidence = intent_model().predict(message)
        relaxed = (result.get("status_intent") == "clarify" and intent == "problem"
                   and intent_confidence >= MODEL_MIN_CONFIDENCE)
        art = _pick_article(hits, result.get("category"), relaxed)
        if art:
            # The rule engine's "clarify" path never assessed the problem
            classification = _fallback_classify(conversation_query(message, history), message)
            result.update(
                category=_model_category(conversation_query(message, history)),
                priority=classification["priority"],
                subject=result.get("subject") or message.strip()[:75],
                reply=(
                    f"Here's the fix from our knowledge base — **{art['title']}**:\n\n{art['body']}\n\n"
                    f"**Did this resolve your issue?** If not, I'll connect you with a technician."
                ),
                status_intent="troubleshoot",
                can_resolve=True,
                used_articles=[art],
            )
    return result


def _with_problem_title(result: Dict[str, Any], message: str, history: Sequence[Dict]) -> Dict[str, Any]:
    """Suggested ticket title from the messages that describe the problem."""
    user_messages = [m.get("text") or m.get("body") or "" for m in history
                     if m.get("sender") == "user" or m.get("sender_type") in ("user", "enduser")]
    if not user_messages or user_messages[-1] != message:
        user_messages.append(message)
    title = summarize_title(user_messages, fallback="")
    if title:
        result["subject"] = title
    elif not is_good_title(result.get("subject")):
        result["subject"] = ""
    return result


async def chat_turn(message: str, history: Sequence[Dict], articles: List[Dict]) -> Dict[str, Any]:
    """One assistant turn. `articles` are the published KB articles."""
    hits = KnowledgeIndex(articles).search(conversation_query(message, history), limit=5, min_score=0.5)
    if ai_enabled():
        reply = await _claude_turn(message, history, [h for h in hits if h.score >= 1.0][:3])
        if reply:
            return reply
        logger.info("Claude unavailable for this turn; using the rule-based assistant")
    return _with_problem_title(await _offline_turn(message, history, articles, hits), message, history)
