"""
Retitle tickets that were created from a chat before titles were summarised
(e.g. a ticket called "Hi" whose conversation was really about a VPN).

Usage (from backend/):
    python scripts/fix_chat_ticket_titles.py           # preview only
    python scripts/fix_chat_ticket_titles.py --apply   # write the changes
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.summary import is_good_title, is_substantive, summarize_description, summarize_title  # noqa: E402
from database import SessionLocal  # noqa: E402
import models  # noqa: E402


def main(apply: bool) -> None:
    db = SessionLocal()
    changed = 0
    try:
        for ticket in db.query(models.Ticket).order_by(models.Ticket.id).all():
            if is_good_title(ticket.subject):
                continue
            user_messages = [m.body for m in ticket.messages if m.sender_type == "user"]
            title = summarize_title(user_messages, fallback="")
            if not title:
                print(f"  #{ticket.id}: {ticket.subject!r} — no problem described in the chat, left as is")
                continue
            print(f"  #{ticket.id}: {ticket.subject!r} -> {title!r}")
            ticket.subject = title
            if not is_substantive(ticket.description):
                ticket.description = summarize_description(user_messages) or title
            changed += 1
        if apply:
            db.commit()
            print(f"\nUpdated {changed} ticket(s).")
        else:
            db.rollback()
            print(f"\n{changed} ticket(s) would change. Run with --apply to save.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
