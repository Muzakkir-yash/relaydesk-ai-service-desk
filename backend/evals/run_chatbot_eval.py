"""
Score the support chatbot against evals/chatbot_cases.json.

Each case replays a user's messages turn by turn (the bot's replies are fed
back into the history, exactly like the chat page) and checks the final turn:
  - intent:   did it clarify / troubleshoot / resolve / escalate correctly?
  - category / priority, when the case specifies them
  - grounding: does the reply mention what it should?

Usage (from backend/, against a COPY of your database — reads only):
    python evals/run_chatbot_eval.py
    python evals/run_chatbot_eval.py --only phishing --verbose

Uses the free offline engine. (Only if ENABLE_PAID_AI=true and a key is set would it
call the paid Claude API — that is switched off in this project.)
"""

import argparse
import asyncio
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.assistant import chat_turn  # noqa: E402
from ai.client import ai_enabled  # noqa: E402
from config import settings  # noqa: E402
from database import SessionLocal  # noqa: E402
import models  # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_SETS = {"main": "chatbot_cases.json", "holdout": "chatbot_holdout_cases.json", "fresh": "chatbot_fresh_cases.json",
             "fresh2": "chatbot_fresh2_cases.json", "fresh3": "chatbot_fresh3_cases.json",
             "fresh4": "chatbot_fresh4_cases.json"}


def load_articles():
    db = SessionLocal()
    try:
        rows = db.query(models.KBArticle).filter(models.KBArticle.status == "published").all()
        return [{"id": r.id, "title": r.title, "body": r.body, "tags": r.tags, "category": r.category,
                 "helpful_count": r.helpful_count or 0, "not_helpful_count": r.not_helpful_count or 0} for r in rows]
    finally:
        db.close()


async def run_case(case, articles):
    history = []
    result = None
    for message in case["turns"]:
        history.append({"sender": "user", "text": message})
        result = await chat_turn(message, history, articles)
        history.append({"sender": "ai", "text": result["reply"]})

    checks = {"intent": result["status_intent"] in case["expect_intent"]}
    if "expect_category" in case:
        checks["category"] = result["category"] in case["expect_category"]
    if "expect_priority" in case:
        checks["priority"] = result["priority"] in case["expect_priority"]
    if "must_mention_any" in case:
        reply = result["reply"].lower()
        checks["grounding"] = any(word in reply for word in case["must_mention_any"])
    return result, checks


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", choices=sorted(CASE_SETS), default="main",
                        help="main = cases used while improving the bot; holdout/fresh = cases for an honest score")
    parser.add_argument("--only", help="run cases whose name contains this text")
    parser.add_argument("--verbose", action="store_true", help="print every reply")
    args = parser.parse_args()

    cases = json.load(open(os.path.join(EVAL_DIR, CASE_SETS[args.set]), encoding="utf-8"))
    if args.only:
        cases = [c for c in cases if args.only.lower() in c["name"].lower()]
    articles = load_articles()
    mode = f"Claude ({settings.ANTHROPIC_MODEL})" if ai_enabled() else "offline rule-based engine"
    print(f"Chatbot eval — {len(cases)} cases, {len(articles)} published KB articles, mode: {mode}\n")

    totals, passed_cases = {}, 0
    for case in cases:
        result, checks = await run_case(case, articles)
        ok = all(checks.values())
        passed_cases += ok
        for name, value in checks.items():
            hit, seen = totals.get(name, (0, 0))
            totals[name] = (hit + value, seen + 1)
        failed = [n for n, v in checks.items() if not v]
        print(f"  {'PASS' if ok else 'FAIL'}  {case['name']:<28} intent={result['status_intent']:<12} "
              f"cat={result['category'] or '-':<9} pri={result['priority'] or '-':<8}"
              + (f"  ✗ {', '.join(failed)}" if failed else ""))
        if args.verbose or not ok:
            print("        " + result["reply"][:300].replace("\n", " ") + ("…" if len(result["reply"]) > 300 else ""))

    print("\nScores")
    for name, (hit, seen) in totals.items():
        print(f"  {name:<10} {hit}/{seen}  ({100 * hit / seen:.0f}%)")
    print(f"  {'overall':<10} {passed_cases}/{len(cases)} cases fully correct ({100 * passed_cases / len(cases):.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
