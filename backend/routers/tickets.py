"""
Ticket endpoints — all phases wired in here.

Phase 1: CRUD (no AI)
Phase 2: AI classify on ticket create
Phase 3: AI deflect, fixed/still-broken confirmation
Phase 4: AI handover briefing on escalate
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user, require_role
from audit import write_audit
import models, schemas
from ai.classifier import classify_ticket
from ai.deflector import deflect_ticket, generate_ai_chat_reply, STOPWORDS
from ai.briefing import generate_briefing
from ai.assistant import chat_turn
from ai.learning import draft_article

logger = logging.getLogger("relaydesk.tickets")

router = APIRouter(prefix="/tickets", tags=["tickets"])

STAFF_ROLES = ("technician", "admin")
OPEN_STATUSES = ("new", "ai_handling", "escalated", "assigned", "in_progress")
CLOSED_STATUSES = ("resolved", "closed", "deflected")
# Tickets already sitting with a human — escalating again would be a no-op
HUMAN_QUEUE_STATUSES = ("escalated", "assigned", "in_progress")
VALID_CATEGORIES = {"hardware", "software", "network", "access", "account", "general", "other"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}

SLA_MINUTES = {"critical": 60, "high": 240, "medium": 480, "low": 1440}

PRIORITY_WEIGHTS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

PRIORITY_TIERS = {
    "critical": "L3",  # Level 3: Infrastructure / Principal / Critical Outages
    "high": "L2",      # Level 2: Systems & Network Specialists
    "medium": "L1",    # Level 1: Service Desk / Application Triage
    "low": "L1",       # Level 1: Service Desk / Password & General
}

# Demo fallbacks for the device panel when the user has no primary device on file
DEFAULT_DEVICE = {
    "device_name": "CORP-LAPTOP-W11-842",
    "device_os": "Windows 11 Enterprise (Build 23H2)",
    "ip_address": "10.14.88.24",
    "subnet_vlan": "VLAN 20 (HQ Floor 3 - Engineering)",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "asset_tag": "AST-84291",
    "serial_number": "PF39X8K2",
    "last_reboot": "3 days ago (Uptime: 74h 12m)",
    "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
    "hardware_specs": "Intel i7-1370P | 32 GB RAM | 512 GB NVMe",
    "domain_join": "CORP.INTERNAL (Hybrid / Intune Compliant)",
}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _get_ticket_or_404(ticket_id: int, db: Session) -> models.Ticket:
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _is_staff(user: models.User) -> bool:
    return user.role in STAFF_ROLES


def _check_ticket_access(ticket: models.Ticket, user: models.User):
    if not _is_staff(user) and ticket.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied: You can only access your own tickets")


def _sla_due(priority: Optional[str]) -> datetime:
    return datetime.utcnow() + timedelta(minutes=SLA_MINUTES.get(priority or "medium", 480))


def _user_primary_device(user: models.User) -> Dict[str, Any]:
    device = getattr(user, "primary_device", None) or {}
    if isinstance(device, str):
        try:
            device = json.loads(device)
        except ValueError:
            device = {"device_name": device}
    return device if isinstance(device, dict) else {}


def _device_context(user: models.User, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Device/asset fields for a new ticket: explicit payload values win,
    then the user's registered device, then demo defaults."""
    overrides = overrides or {}
    device = _user_primary_device(user)
    ctx = {field: overrides.get(field) or device.get(field) or default for field, default in DEFAULT_DEVICE.items()}
    ctx["office_location"] = (
        overrides.get("office_location") or device.get("office_location") or device.get("branch") or "HQ - New York"
    )
    return ctx


def _transcript_messages(raw_messages: List[dict]) -> List[Dict[str, str]]:
    """Normalise chat-widget messages ({sender,text} or {sender_type,body})."""
    out = []
    for m in raw_messages:
        if not isinstance(m, dict):
            continue
        body = str(m.get("text") or m.get("body") or "").strip()
        if not body:
            continue
        is_user = m.get("sender") == "user" or m.get("sender_type") in ("user", "enduser")
        out.append({"sender_type": "user" if is_user else "ai", "body": body[:20000]})
    return out


def _clean_choice(value: Optional[str], allowed: set, default: str) -> str:
    value = (value or "").lower()
    return value if value in allowed else default


_WORD_RE = re.compile(r"[a-z0-9]+")


def _keywords(text: str) -> set:
    return {w for w in _WORD_RE.findall((text or "").lower()) if len(w) > 2 and w not in STOPWORDS}


def _find_similar_tickets(db: Session, ticket: models.Ticket, limit: int = 5) -> List[Dict[str, Any]]:
    """Rank recently closed tickets by keyword overlap with this one,
    boosting the same category, so the briefing cites genuinely related cases."""
    candidates = (
        db.query(models.Ticket)
        .filter(models.Ticket.status.in_(CLOSED_STATUSES), models.Ticket.id != ticket.id)
        .order_by(models.Ticket.id.desc())
        .limit(300)
        .all()
    )
    target = _keywords(f"{ticket.subject} {ticket.description}")
    scored = []
    for c in candidates:
        overlap = len(target & _keywords(f"{c.subject} {c.description}"))
        score = overlap + (2 if ticket.category and c.category == ticket.category else 0)
        if overlap:
            scored.append((score, c))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [{"id": c.id, "subject": c.subject, "description": c.description} for _, c in scored[:limit]]


async def _create_briefing(db: Session, ticket: models.Ticket, messages: List[dict], ai_tried: str) -> Dict[str, Any]:
    """AI Job 3: generate the handover briefing and upsert it (one per ticket)."""
    similar = _find_similar_tickets(db, ticket)
    data = await generate_briefing(
        ticket={"subject": ticket.subject, "description": ticket.description},
        messages=messages,
        ai_tried=ai_tried,
        similar_tickets=similar,
    )
    fields = {
        "summary": data.get("summary", ""),
        "user_tried": data.get("user_tried", ""),
        "ai_tried": data.get("ai_tried", ""),
        "likely_causes": data.get("likely_causes", []),
        "suggested_steps": data.get("suggested_steps", []),
        "related_ticket_ids": data.get("related_tickets", []),
        "generated_at": datetime.utcnow(),
    }
    briefing = db.query(models.HandoverBriefing).filter_by(ticket_id=ticket.id).first()
    if briefing:
        for key, value in fields.items():
            setattr(briefing, key, value)
    else:
        db.add(models.HandoverBriefing(ticket_id=ticket.id, **fields))
    db.add(models.AIAction(
        ticket_id=ticket.id,
        action_type="handover",
        input_snapshot=json.dumps({"messages_count": len(messages), "similar_ticket_ids": [s["id"] for s in similar]}),
        output_snapshot=json.dumps(data),
    ))
    db.commit()
    return data


def _published_articles(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(models.KBArticle).filter(models.KBArticle.status == "published").all()
    return [{
        "id": r.id, "title": r.title, "body": r.body, "tags": r.tags, "category": r.category,
        "helpful_count": r.helpful_count or 0, "not_helpful_count": r.not_helpful_count or 0,
    } for r in rows]


def _record_article_feedback(db: Session, article_ids: List[int], helpful: bool) -> None:
    """The chatbot suggested these articles; the session ended fixed (helpful)
    or escalated (not helpful). Feeds the knowledge ranking."""
    if not article_ids:
        return
    column = models.KBArticle.helpful_count if helpful else models.KBArticle.not_helpful_count
    db.query(models.KBArticle).filter(models.KBArticle.id.in_(set(article_ids))).update(
        {column: column + 1}, synchronize_session=False
    )


async def _learn_from_resolution(db: Session, ticket: models.Ticket) -> None:
    """Continuous learning: draft a KB article from a technician's fix, for
    staff approval. Never fails the resolve request."""
    try:
        if db.query(models.KBArticle.id).filter(models.KBArticle.source_ticket_id == ticket.id).first():
            return
        messages = [
            {"sender_type": m.sender_type, "body": m.body}
            for m in ticket.messages
            if "Simulated playbook" not in m.body  # demo macros, not a real fix
        ]
        draft = await draft_article(
            {"id": ticket.id, "subject": ticket.subject, "description": ticket.description,
             "category": ticket.category, "tags": ticket.tags},
            messages,
        )
        if not draft:
            return
        category = draft.get("category")
        db.add(models.KBArticle(
            title=str(draft["title"])[:256],
            body=draft["body"],
            tags=str(draft.get("tags") or "")[:512] or None,
            category=category if category in VALID_CATEGORIES else ticket.category,
            source="ai_drafted",
            status="pending_approval",
            source_ticket_id=ticket.id,
        ))
        db.add(models.AIAction(
            ticket_id=ticket.id,
            action_type="kb_draft",
            input_snapshot=json.dumps({"messages_count": len(messages)}),
            output_snapshot=json.dumps(draft),
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("KB draft from ticket #%s failed", ticket.id)


def auto_assign_by_weight(ticket: models.Ticket, db: Session) -> Optional[models.User]:
    """
    Tier-Based & Problem Weight Automated Assignment:
    1. Determines target support level from problem weight:
       - Critical (Weight 4) -> L3 Support Specialist
       - High (Weight 3)     -> L2 Support Specialist
       - Medium (Weight 2)   -> L1 Service Desk (overflow to L2)
       - Low (Weight 1)      -> L1 Service Desk
    2. Filters and scores technicians by:
       - Tier affinity (exact L1/L2/L3 match preferred)
       - Domain specialization match (Network, Hardware, Access)
       - Active weighted backlog load balance
    """
    techs = db.query(models.User).filter(models.User.role.in_(STAFF_ROLES)).all()
    if not techs:
        return None

    pri = ticket.priority or "medium"
    target_tier = PRIORITY_TIERS.get(pri, "L1")
    ticket.target_level = target_tier

    ticket_cat = (ticket.category or "").lower()
    ticket_team = (ticket.suggested_team or "").lower()

    # One query for everyone's active load instead of one query per technician
    active = (
        db.query(models.Ticket.assigned_to, models.Ticket.priority)
        .filter(
            models.Ticket.assigned_to.in_([t.id for t in techs]),
            models.Ticket.status.in_(HUMAN_QUEUE_STATUSES),
            models.Ticket.id != ticket.id,
        )
        .all()
    )
    load: Dict[int, List[str]] = {}
    for assignee, priority in active:
        load.setdefault(assignee, []).append(priority)

    tier_penalties = {
        ("L3", "L1"): 8.0, ("L3", "L2"): 3.0,
        ("L2", "L3"): 2.0, ("L2", "L1"): 4.0,
        ("L1", "L3"): 5.0, ("L1", "L2"): 1.5,
    }

    scored = []
    for tech in techs:
        priorities = load.get(tech.id, [])
        current_load = sum(PRIORITY_WEIGHTS.get(p or "medium", 2) for p in priorities)
        tech_level = tech.support_level or "L1"
        tier_penalty = tier_penalties.get((target_tier, tech_level), 0.0)

        tech_team = (tech.team or "").lower()
        is_specialist = bool(tech_team and (
            (ticket_cat and (tech_team in ticket_cat or ticket_cat in tech_team))
            or (ticket_team and (tech_team in ticket_team or ticket_team in tech_team))
        ))
        effective_load = current_load + tier_penalty - (1.5 if is_specialist else 0.0)
        scored.append((effective_load, len(priorities), tech))

    # Lowest effective load first, tie-breaker by active ticket count
    scored.sort(key=lambda x: (x[0], x[1]))
    chosen = scored[0][2]
    ticket.assigned_to = chosen.id
    return chosen


# ─────────────────────────────────────────────────────────────────
# Create ticket  (Phase 1 + AI Job 1 + AI Job 2)
# ─────────────────────────────────────────────────────────────────
@router.post("", response_model=schemas.TicketOut, status_code=201)
async def create_ticket(
    payload: schemas.TicketCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = models.Ticket(
        user_id=current_user.id,
        subject=payload.subject,
        description=payload.description,
        attachments=payload.attachments,
        status="new",
        **_device_context(current_user, payload.model_dump()),
    )
    db.add(ticket)
    db.flush()
    db.add(models.TicketMessage(
        ticket_id=ticket.id,
        sender_type="user",
        sender_id=current_user.id,
        body=payload.description,
        attachments=payload.attachments,
    ))
    db.commit()
    db.refresh(ticket)

    # ── AI Job 1: Classify & Route ──────────────────────────────
    try:
        classification = await classify_ticket(subject=payload.subject, description=payload.description)
        ticket.category = classification.get("category")
        ticket.priority = classification.get("priority")
        ticket.suggested_team = classification.get("suggested_team")
        ticket.tags = classification.get("tags", [])
        ticket.mood = classification.get("mood")
        ticket.language = classification.get("language")
        ticket.status = "ai_handling"
        ticket.sla_due = _sla_due(ticket.priority)

        # ── Auto-Assign by Problem Weight & Workload Balancing ──
        auto_assign_by_weight(ticket, db)

        db.add(models.AIAction(
            ticket_id=ticket.id,
            action_type="classify",
            input_snapshot=json.dumps({"subject": payload.subject, "description": payload.description}),
            output_snapshot=json.dumps(classification),
        ))
        db.commit()
    except Exception:
        # AI failure is non-fatal — the ticket exists, it is just unclassified
        db.rollback()
        logger.exception("AI classify failed for ticket #%s", ticket.id)

    write_audit(db, current_user, "ticket_created", "ticket", ticket.id,
                f"Ticket #{ticket.id} created: '{payload.subject}'")

    # ── AI Job 2: Deflection attempt ────────────────────────────
    try:
        kb_models = db.query(models.KBArticle).filter(models.KBArticle.status == "published").all()
        kb_articles = [{"id": r.id, "title": r.title, "body": r.body, "tags": r.tags} for r in kb_models]

        deflection = await deflect_ticket(
            subject=payload.subject,
            description=payload.description,
            kb_articles=kb_articles,
        )
        db.add(models.AIAction(
            ticket_id=ticket.id,
            action_type="deflect_attempt",
            input_snapshot=json.dumps({"subject": payload.subject, "kb_count": len(kb_articles)}),
            output_snapshot=json.dumps(deflection),
        ))
        # Always show the AI's reply — when it cannot resolve, the reply asks
        # for clarification, which is still more useful than silence.
        if deflection.get("answer"):
            db.add(models.TicketMessage(ticket_id=ticket.id, sender_type="ai", body=deflection["answer"]))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("AI deflect failed for ticket #%s", ticket.id)

    db.refresh(ticket)
    return ticket


# ─────────────────────────────────────────────────────────────────
# Confirm resolution or escalate (Phase 3 UI buttons)
# ─────────────────────────────────────────────────────────────────
@router.post("/{ticket_id}/confirm-resolved", response_model=schemas.TicketOut)
def confirm_resolved(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    _check_ticket_access(ticket, current_user)
    if ticket.status == "deflected":
        return ticket
    # Only count it as an AI deflection if no human has picked it up yet,
    # otherwise the deflection-rate metric would be inflated.
    if ticket.status not in ("new", "ai_handling"):
        raise HTTPException(status_code=409, detail=f"Ticket is '{ticket.status}' and is being handled by a technician")
    ticket.status = "deflected"
    ticket.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    write_audit(db, current_user, "ticket_deflected", "ticket", ticket_id,
                f"Ticket #{ticket_id} confirmed resolved via self-service by user {current_user.id}")
    return ticket


# ─────────────────────────────────────────────────────────────────
# AI Conversational Triage (Intake Chatbot)
# ─────────────────────────────────────────────────────────────────
@router.post("/ai-triage/chat", response_model=schemas.AITriageChatResponse)
async def ai_triage_chat(
    payload: schemas.AITriageChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    First-line support chat. The assistant answers from the company knowledge
    base, asks clarifying questions, and returns status_intent "resolved" when
    the user confirms a fix or "escalate" when a technician is needed.
    """
    triage_result = await chat_turn(
        message=payload.message,
        history=(payload.chat_history or [])[-50:],
        articles=_published_articles(db),
    )
    return schemas.AITriageChatResponse(
        reply=triage_result["reply"],
        subject=triage_result["subject"],
        category=triage_result["category"],
        priority=triage_result["priority"],
        status_intent=triage_result["status_intent"],
        can_resolve=triage_result["can_resolve"],
        used_articles=triage_result.get("used_articles", []),
    )


@router.post("/ai-triage/resolve")
def ai_triage_resolve(
    payload: schemas.AITriageResolveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Confirms that the AI chatbot successfully resolved the issue via self-service.
    Creates a ticket record in status 'deflected' and updates deflection metrics.
    """
    transcript = _transcript_messages(payload.messages)
    first_msg = next((m["body"] for m in transcript if m["sender_type"] == "user"), "")
    subject = (payload.subject or first_msg[:75] or "Self-Service IT Resolution")[:256]

    ticket = models.Ticket(
        user_id=current_user.id,
        subject=subject,
        description=first_msg or subject,
        category=_clean_choice(payload.category, VALID_CATEGORIES, "general"),
        priority=_clean_choice(payload.priority, VALID_PRIORITIES, "low"),
        status="deflected",
        resolved_at=datetime.utcnow(),
        **_device_context(current_user, {"device_name": payload.device_name, "office_location": payload.office_location}),
    )
    db.add(ticket)
    db.flush()

    for m in transcript:
        db.add(models.TicketMessage(
            ticket_id=ticket.id,
            sender_type=m["sender_type"],
            sender_id=current_user.id if m["sender_type"] == "user" else None,
            body=m["body"],
        ))
    db.add(models.AIAction(
        ticket_id=ticket.id,
        action_type="deflect_attempt",
        input_snapshot=json.dumps({"subject": subject}),
        output_snapshot=json.dumps({"status": "deflected", "resolved_by_user": True,
                                    "used_article_ids": payload.used_article_ids}),
    ))
    _record_article_feedback(db, payload.used_article_ids, helpful=True)
    db.commit()

    write_audit(db, current_user, "ticket_deflected", "ticket", ticket.id,
                f"Ticket #{ticket.id} resolved and deflected via AI Chatbot by user {current_user.id}")

    return {
        "ticket_id": ticket.id,
        "status": "deflected",
        "subject": ticket.subject,
        "message": "Ticket successfully resolved via AI self-service."
    }


@router.post("/ai-triage/escalate")
async def ai_triage_escalate(
    payload: schemas.AITriageEscalateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Seamless escalation: Turns an unresolved AI Chatbot triage session into a human support ticket.
    Generates the Handover Briefing and auto-assigns an L1/L2/L3 technician by workload.
    """
    transcript = _transcript_messages(payload.messages)
    first_msg = next((m["body"] for m in transcript if m["sender_type"] == "user"), "")
    subject = (payload.subject or first_msg[:75] or "Escalated IT Support Request")[:256]
    priority = _clean_choice(payload.priority, VALID_PRIORITIES, "medium")

    ticket = models.Ticket(
        user_id=current_user.id,
        subject=subject,
        description=first_msg or subject,
        category=_clean_choice(payload.category, VALID_CATEGORIES, "other"),
        priority=priority,
        status="escalated",
        sla_due=_sla_due(priority),
        **_device_context(current_user, {"device_name": payload.device_name, "office_location": payload.office_location}),
    )
    db.add(ticket)
    db.flush()

    now = str(datetime.utcnow())
    for m in transcript:
        db.add(models.TicketMessage(
            ticket_id=ticket.id,
            sender_type=m["sender_type"],
            sender_id=current_user.id if m["sender_type"] == "user" else None,
            body=m["body"],
        ))
    _record_article_feedback(db, payload.used_article_ids, helpful=False)
    db.commit()

    # Everything the assistant tried, so the briefing doesn't suggest it again
    ai_tried_text = "\n---\n".join(m["body"][:600] for m in transcript if m["sender_type"] == "ai")[-2500:]
    briefing_data: Dict[str, Any] = {}
    try:
        briefing_data = await _create_briefing(
            db, ticket, [{**m, "created_at": now} for m in transcript], ai_tried_text
        )
    except Exception:
        db.rollback()
        logger.exception("AI handover briefing failed for ticket #%s", ticket.id)

    assigned_tech = auto_assign_by_weight(ticket, db)
    ticket.status = "assigned" if assigned_tech else "escalated"

    tech_name = assigned_tech.name if assigned_tech else "IT Support Specialist"
    tech_team = (assigned_tech.team or "Help Desk") if assigned_tech else "Help Desk"
    sla_hours = SLA_MINUTES.get(priority, 480) // 60
    db.add(models.TicketMessage(
        ticket_id=ticket.id,
        sender_type="ai",
        body=(
            f"📋 **Ticket #{ticket.id} Escalated to Human Support**\n\n"
            f"• **Assigned Specialist**: {tech_name} ({tech_team})\n"
            f"• **Priority Level**: {priority.capitalize()}\n"
            f"• **Target SLA**: {sla_hours} hours\n\n"
            f"Our AI Handover Briefing has been delivered to {tech_name} with your troubleshooting notes. A technician will contact you directly."
        )
    ))
    db.commit()
    db.refresh(ticket)

    write_audit(db, current_user, "ticket_escalated", "ticket", ticket.id,
                f"Ticket #{ticket.id} escalated from AI Chatbot to {tech_name}")

    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "subject": ticket.subject,
        "priority": ticket.priority,
        "category": ticket.category,
        "assigned_to": assigned_tech.id if assigned_tech else None,
        "assigned_tech_name": tech_name,
        "assigned_tech_team": tech_team,
        "sla_due": str(ticket.sla_due) if ticket.sla_due else None,
        "briefing_summary": briefing_data.get("summary", ""),
        "redirect_url": f"/ticket.html?id={ticket.id}"
    }


# ─────────────────────────────────────────────────────────────────
# List tickets
# ─────────────────────────────────────────────────────────────────
@router.get("", response_model=List[schemas.TicketListItem])
def list_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Ticket)

    # STRICT USER ISOLATION: End users only ever see their own tickets
    if not _is_staff(current_user):
        q = q.filter(models.Ticket.user_id == current_user.id)
    elif assigned_to:
        q = q.filter(models.Ticket.assigned_to == assigned_to)

    if status:
        q = q.filter(models.Ticket.status == status)
    if priority:
        q = q.filter(models.Ticket.priority == priority)
    if category:
        q = q.filter(models.Ticket.category == category)

    q = q.order_by(models.Ticket.created_at.desc()).offset(offset)
    if limit:
        q = q.limit(limit)
    return q.all()


# ─────────────────────────────────────────────────────────────────
# Get single ticket
# ─────────────────────────────────────────────────────────────────
@router.get("/{ticket_id}", response_model=schemas.TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    _check_ticket_access(ticket, current_user)
    return ticket


def _validate_assignee(db: Session, user_id: int) -> None:
    assignee = db.query(models.User).filter(models.User.id == user_id).first()
    if not assignee or assignee.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail="assigned_to must be a technician or admin")


# ─────────────────────────────────────────────────────────────────
# Update ticket (assign / change status / priority)
# ─────────────────────────────────────────────────────────────────
@router.patch("/{ticket_id}", response_model=schemas.TicketOut)
async def update_ticket(
    ticket_id: int,
    payload: schemas.TicketUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*STAFF_ROLES)),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    changes = payload.model_dump(exclude_none=True)
    if payload.status:
        ticket.status = payload.status
        if payload.status in ("resolved", "closed"):
            ticket.resolved_at = datetime.utcnow()
    if payload.assigned_to is not None:
        _validate_assignee(db, payload.assigned_to)
        ticket.assigned_to = payload.assigned_to
        if ticket.status == "escalated":
            ticket.status = "assigned"
    if payload.priority and payload.priority != ticket.priority:
        ticket.priority = payload.priority
        ticket.sla_due = _sla_due(payload.priority)
    if payload.category:
        ticket.category = payload.category
    db.commit()
    db.refresh(ticket)
    write_audit(db, current_user, "ticket_updated", "ticket", ticket_id, f"Ticket #{ticket_id} updated: {changes}")
    if payload.status == "resolved":
        await _learn_from_resolution(db, ticket)
    return ticket


# ─────────────────────────────────────────────────────────────────
# Get messages for ticket
# ─────────────────────────────────────────────────────────────────
@router.get("/{ticket_id}/messages", response_model=List[schemas.MessageOut])
def get_ticket_messages(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    _check_ticket_access(ticket, current_user)
    return ticket.messages


# ─────────────────────────────────────────────────────────────────
# Add message
# ─────────────────────────────────────────────────────────────────
@router.post("/{ticket_id}/messages", response_model=schemas.MessageOut, status_code=201)
async def add_message(
    ticket_id: int,
    payload: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    _check_ticket_access(ticket, current_user)

    sender_type = "technician" if _is_staff(current_user) else "user"
    msg = models.TicketMessage(
        ticket_id=ticket_id,
        sender_type=sender_type,
        sender_id=current_user.id,
        body=payload.body,
        attachments=payload.attachments,
    )
    db.add(msg)

    # Move to in_progress when technician first replies
    if sender_type == "technician" and ticket.status in ("assigned", "escalated"):
        ticket.status = "in_progress"

    db.commit()
    db.refresh(msg)

    # While the AI still owns the ticket, answer the user's follow-up
    if sender_type == "user" and ticket.status == "ai_handling":
        try:
            chat_history = [{"sender_type": m.sender_type, "body": m.body} for m in ticket.messages]
            ai_reply = await generate_ai_chat_reply(
                subject=ticket.subject,
                description=ticket.description,
                chat_history=chat_history,
                new_message=payload.body,
            )
            if ai_reply:
                db.add(models.TicketMessage(ticket_id=ticket_id, sender_type="ai", body=ai_reply))
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("AI chat follow-up failed for ticket #%s", ticket_id)

    return msg


# ─────────────────────────────────────────────────────────────────
# Escalate → AI Job 3: Handover Briefing  ⭐
# ─────────────────────────────────────────────────────────────────
@router.post("/{ticket_id}/escalate", response_model=schemas.TicketOut)
async def escalate_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    _check_ticket_access(ticket, current_user)
    if ticket.status in HUMAN_QUEUE_STATUSES:
        raise HTTPException(status_code=409, detail="Ticket is already with a technician")

    ticket.status = "escalated"
    ticket.resolved_at = None
    if not ticket.sla_due or ticket.sla_due < datetime.utcnow():
        ticket.sla_due = _sla_due(ticket.priority)
    db.commit()

    messages = [
        {"sender_type": m.sender_type, "body": m.body, "created_at": str(m.created_at)}
        for m in ticket.messages
    ]

    # What the AI already tried = the latest deflection answer
    ai_tried_text = ""
    for a in sorted(ticket.ai_actions, key=lambda a: a.id, reverse=True):
        if a.action_type == "deflect_attempt" and a.output_snapshot:
            try:
                ai_tried_text = json.loads(a.output_snapshot).get("answer", "")
            except ValueError:
                pass
            if ai_tried_text:
                break

    try:
        await _create_briefing(db, ticket, messages, ai_tried_text)
    except Exception:
        db.rollback()
        logger.exception("AI briefing failed for ticket #%s", ticket_id)

    assigned_tech = auto_assign_by_weight(ticket, db)
    ticket.status = "assigned" if assigned_tech else "escalated"

    db.add(models.TicketMessage(
        ticket_id=ticket.id,
        sender_type="ai",
        body="📋 **Ticket Escalated to IT Support**\n\nI have prepared a diagnostic handover briefing of your issue and transferred this ticket to our technician queue. An IT specialist is reviewing your case and will reply directly here.",
    ))
    db.commit()

    write_audit(db, current_user, "ticket_escalated", "ticket", ticket_id,
                f"Ticket #{ticket_id} escalated to technician by user {current_user.id}")

    db.refresh(ticket)
    return ticket


# ─────────────────────────────────────────────────────────────────
# Resolve ticket
# ─────────────────────────────────────────────────────────────────
@router.post("/{ticket_id}/resolve", response_model=schemas.TicketOut)
async def resolve_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*STAFF_ROLES)),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    ticket.status = "resolved"
    ticket.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    write_audit(db, current_user, "ticket_resolved", "ticket", ticket_id,
                f"Ticket #{ticket_id} resolved by {current_user.name}")
    await _learn_from_resolution(db, ticket)
    db.refresh(ticket)
    return ticket


# End users may only move their own ticket into these states
ENDUSER_ALLOWED_STATUSES = {"deflected", "ai_deflected", "escalated", "closed"}


# ─────────────────────────────────────────────────────────────────
# Flexible status update alias (handles all UI status changes safely)
# ─────────────────────────────────────────────────────────────────
@router.patch("/{ticket_id}/status", response_model=schemas.TicketOut)
async def update_ticket_status_flexible(
    ticket_id: int,
    payload: schemas.TicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    _check_ticket_access(ticket, current_user)
    new_status = payload.status
    if not new_status:
        return ticket
    if not _is_staff(current_user) and new_status not in ENDUSER_ALLOWED_STATUSES:
        raise HTTPException(status_code=403, detail=f"End users cannot set status '{new_status}'")

    if new_status in ("ai_deflected", "deflected"):
        return confirm_resolved(ticket_id, db, current_user)
    if new_status == "escalated":
        return await escalate_ticket(ticket_id, db, current_user)

    ticket.status = new_status
    if new_status in ("resolved", "closed"):
        ticket.resolved_at = datetime.utcnow()
    if payload.assigned_to is not None and _is_staff(current_user):
        _validate_assignee(db, payload.assigned_to)
        ticket.assigned_to = payload.assigned_to
    db.commit()
    db.refresh(ticket)
    write_audit(db, current_user, "ticket_status_updated", "ticket", ticket_id, f"Status updated to {new_status}")
    if new_status == "resolved" and _is_staff(current_user):
        await _learn_from_resolution(db, ticket)
        db.refresh(ticket)
    return ticket


# ─────────────────────────────────────────────────────────────────
# Rate ticket (end users, after resolution)
# ─────────────────────────────────────────────────────────────────
@router.post("/{ticket_id}/rate", response_model=schemas.TicketRatingOut, status_code=201)
def rate_ticket(
    ticket_id: int,
    payload: schemas.TicketRatingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your ticket")
    if ticket.status not in CLOSED_STATUSES:
        raise HTTPException(status_code=409, detail="Only resolved tickets can be rated")
    if db.query(models.TicketRating).filter_by(ticket_id=ticket_id).first():
        raise HTTPException(status_code=400, detail="Already rated")
    rating = models.TicketRating(ticket_id=ticket_id, rating=payload.rating, comment=payload.comment)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


# ─────────────────────────────────────────────────────────────────
# Technician Playbooks & Remote Remediation Macros ⚡
# ─────────────────────────────────────────────────────────────────
PLAYBOOK_CATALOG = {
    "ad_password_reset": {
        "title": "Reset Active Directory Password & Send Temp Token",
        "category": "access",
        "cmd_pattern": "Set-ADAccountPassword -Identity '{user_email}' -Reset; Grant-MfaBypass -User '{user_email}' -Hours 4",
        "render_body": lambda ctx: (
            f"🔑 **Automated IT Playbook Executed: Active Directory Password & Token Reset**\n\n"
            f"- **Target Account:** `{ctx['user_email']}` (Domain: `CORP.INTERNAL`)\n"
            f"- **Domain Controller:** `DC01-HQ.CORP.INTERNAL`\n"
            f"- **One-Time Passkey Token:** `{ctx['temp_token']}`\n"
            f"- **Force Password Change on Next Logon:** `Enabled`\n"
            f"- **MFA Token Sync:** `Bypass window provisioned (Valid for 4 hours)`\n\n"
            f"```powershell\n"
            f"PS C:\\> Set-ADAccountPassword -Identity '{ctx['user_email']}' -Reset -NewPassword $SecureToken\n"
            f"PS C:\\> Set-ADUser -Identity '{ctx['user_email']}' -ChangePasswordAtLogon $true\n"
            f"[SUCCESS] AD Kerberos ticket invalidated. Temp passkey generated: {ctx['temp_token']}\n"
            f"```\n\n"
            f"Please use this temporary token at https://sso.company.com to authenticate and set a new compliant password."
        ),
        "render_output": lambda ctx: (
            f"Connecting to DC01-HQ.CORP.INTERNAL via WinRM...\n"
            f"[OK] Authentication verified for operator: {ctx['tech_name']}\n"
            f"[OK] Querying AD Object: CN={ctx['user_name']},OU=Users,DC=corp,DC=internal\n"
            f"[OK] Account Lockout State: UNLOCKED\n"
            f"[OK] Password reset executed. Temporary token issued: {ctx['temp_token']}\n"
            f"[OK] MFA Sync Token push dispatched to registered device.\n"
            f"Exit Code: 0 (Success)"
        ),
    },
    "remote_dns_flush": {
        "title": "Flush Remote DNS & Restart AnyConnect Adapter",
        "category": "network",
        "cmd_pattern": "Invoke-Command -ComputerName '{device_name}' -ScriptBlock {{ ipconfig /flushdns; Restart-NetAdapter -Name 'Cisco AnyConnect*' }}",
        "render_body": lambda ctx: (
            f"🌐 **Automated IT Playbook Executed: Remote DNS Flush & Adapter Restart**\n\n"
            f"- **Target Hostname:** `{ctx['device_name']}` (`{ctx['ip_address']}`)\n"
            f"- **Network Adapter:** `Cisco AnyConnect Secure Mobility Client Virtual Miniport`\n"
            f"- **DNS Resolver Cache:** `Flushed & Cleared (0 cached records)`\n"
            f"- **Gateway Latency:** `TCP 443 -> vpn.company.com (4.18ms, Handshake OK)`\n\n"
            f"```powershell\n"
            f"PS C:\\> ipconfig /flushdns\n"
            f"Windows IP Configuration\n"
            f"Successfully flushed the DNS Resolver Cache.\n"
            f"PS C:\\> Restart-NetAdapter -Name 'Cisco AnyConnect*'\n"
            f"PS C:\\> Test-NetConnection -ComputerName 'vpn.company.com' -Port 443\n"
            f"TcpTestSucceeded : True (Latency: 4.18ms)\n"
            f"```\n\n"
            f"Remote network interface cycle completed successfully."
        ),
        "render_output": lambda ctx: (
            f"Establishing WinRM session to {ctx['device_name']} ({ctx['ip_address']})...\n"
            f"[OK] WinRM Connected (Kerberos Auth)\n"
            f"Executing: ipconfig /flushdns...\n"
            f"  -> Successfully flushed the DNS Resolver Cache.\n"
            f"Executing: Restart-NetAdapter -Name 'Cisco AnyConnect*' -Confirm:$false...\n"
            f"  -> Adapter status: DOWN -> UP (Link Speed: 1000 Mbps)\n"
            f"Executing: Test-NetConnection -ComputerName 'vpn.company.com' -Port 443...\n"
            f"  -> RemoteAddress: 10.200.1.1, TcpTestSucceeded: True, RTT: 4.18ms\n"
            f"Exit Code: 0 (Success)"
        ),
    },
    "exchange_resync": {
        "title": "Re-sync Exchange Mailbox & Rebuild Outlook Profile",
        "category": "software",
        "cmd_pattern": "Invoke-Command -ComputerName '{device_name}' -ScriptBlock {{ Test-ExchangeAutodiscover -Mailbox '{user_email}'; Reset-OutlookCache }}",
        "render_body": lambda ctx: (
            f"📧 **Automated IT Playbook Executed: Exchange Mailbox & OST Re-sync**\n\n"
            f"- **Target User:** `{ctx['user_email']}`\n"
            f"- **Target Workstation:** `{ctx['device_name']}`\n"
            f"- **Exchange Environment:** `Microsoft 365 Exchange Online (Tenant: CORP-M365)`\n"
            f"- **Action Performed:** `Purged cached Outlook OST views, refreshed Autodiscover XML payload, re-authenticated MAPI endpoints`\n\n"
            f"```powershell\n"
            f"PS C:\\> Test-ExchangeAutodiscover -Mailbox '{ctx['user_email']}'\n"
            f"Autodiscover Response: HTTP/2 200 OK (MAPI/HTTP Enabled)\n"
            f"Mailbox Server: outlook.office365.com (EWS Status: Healthy)\n"
            f"[SUCCESS] OST profile sync complete. Folder index invalidated.\n"
            f"```\n\n"
            f"Please restart Microsoft Outlook to load the synchronized folder hierarchy."
        ),
        "render_output": lambda ctx: (
            f"Connecting to M365 Exchange Online PowerShell module...\n"
            f"[OK] Authenticated session active for tenant CORP-M365\n"
            f"Querying mailbox configuration for {ctx['user_email']}...\n"
            f"  -> RecipientTypeDetails: UserMailbox\n"
            f"  -> TotalItemSize: 4.82 GB (Quota: 50 GB)\n"
            f"Invoking remote Outlook cache clear on {ctx['device_name']}...\n"
            f"  -> Autodiscover cache cleared\n"
            f"  -> MAPI connection endpoints refreshed\n"
            f"Exit Code: 0 (Success)"
        ),
    },
    "edr_scan": {
        "title": "Trigger Endpoint EDR Fast Scan (CrowdStrike Falcon)",
        "category": "hardware",
        "cmd_pattern": "Invoke-FalconAdmin -Endpoint '{device_name}' -Action RunOnDemandScan -Scope Fast",
        "render_body": lambda ctx: (
            f"🛡️ **Automated IT Playbook Executed: CrowdStrike Falcon On-Demand EDR Scan**\n\n"
            f"- **Target Endpoint:** `{ctx['device_name']}` (`{ctx['ip_address']}`)\n"
            f"- **EDR Sensor Version:** `CrowdStrike Falcon Sensor v7.14.18004.0 (Healthy)`\n"
            f"- **Inspection Scope:** `Memory resident binaries, Autoruns, %TEMP%, Drivers, Running DLLs`\n"
            f"- **Objects Scanned:** `18,419 items` (Scan duration: 24.3s)\n"
            f"- **Threat Assessment:** `0 Threats / 0 Detections (Sensor Status: OPTIMAL)`\n\n"
            f"```text\n"
            f"[CROWDSTRIKE] Host {ctx['device_name']} assigned AID: 9f82ab14c0294711b8\n"
            f"[CROWDSTRIKE] Fast memory heuristic evaluation: CLEAN\n"
            f"[CROWDSTRIKE] Kernel hooks inspection: VERIFIED\n"
            f"[CROWDSTRIKE] On-demand scan completed. Zero threat indicators identified.\n"
            f"```"
        ),
        "render_output": lambda ctx: (
            f"Dispatching real-time sensor API request to CrowdStrike Cloud Control...\n"
            f"[OK] Agent AID: 9f82ab14c0294711b8 located on network (RF status: ACTIVE)\n"
            f"[OK] Command: RunOnDemandScan -Type 'RapidMemoryAndAutoruns'\n"
            f"[OK] Sensor execution started...\n"
            f"  -> Memory segments examined: 4,102\n"
            f"  -> File system hashes checked: 14,317\n"
            f"  -> Malicious behaviors detected: 0\n"
            f"Scan finished in 24.3s. Host is clean and compliant.\n"
            f"Exit Code: 0 (Success)"
        ),
    },
    "gpupdate_force": {
        "title": "Force Group Policy & Kerberos Ticket Sync",
        "category": "access",
        "cmd_pattern": "Invoke-Command -ComputerName '{device_name}' -ScriptBlock {{ gpupdate /force; klist purge; klist get krbtgt }}",
        "render_body": lambda ctx: (
            f"⚡ **Automated IT Playbook Executed: Group Policy Refresh & Kerberos Sync**\n\n"
            f"- **Target Endpoint:** `{ctx['device_name']}`\n"
            f"- **Domain:** `CORP.INTERNAL`\n"
            f"- **Computer Policy:** `Applied successfully (BitLocker-Enforcement, Windows-Defender-Policy)`\n"
            f"- **User Policy:** `Applied successfully (Default Domain Policy, Drive-Mappings, SecBaseline)`\n"
            f"- **Kerberos TGT:** `Purged and re-issued by DC01-HQ.CORP.INTERNAL`\n\n"
            f"```powershell\n"
            f"PS C:\\> gpupdate /force\n"
            f"Updating policy...\n"
            f"Computer Policy update has completed successfully.\n"
            f"User Policy update has completed successfully.\n"
            f"PS C:\\> klist purge\n"
            f"Purging all tickets: Ticket cache flushed.\n"
            f"PS C:\\> klist get krbtgt\n"
            f"New TGT issued (Kerberos v5 AES-256-CTS-HMAC-SHA1-96)\n"
            f"```"
        ),
        "render_output": lambda ctx: (
            f"Initiating remote WMI/WinRM connection to {ctx['device_name']}...\n"
            f"[OK] Session opened under NT AUTHORITY\\SYSTEM\n"
            f"Executing gpupdate /force...\n"
            f"  -> Computer Policy updated successfully\n"
            f"  -> User Policy updated successfully\n"
            f"Executing klist purge && klist get krbtgt...\n"
            f"  -> 3 cached tickets purged\n"
            f"  -> New Kerberos TGT retrieved from DC01-HQ\n"
            f"Exit Code: 0 (Success)"
        ),
    },
    "restart_spooler": {
        "title": "Clear Print Spooler Queue & Restart Service",
        "category": "hardware",
        "cmd_pattern": "Invoke-Command -ComputerName '{device_name}' -ScriptBlock {{ Stop-Service 'Spooler' -Force; Remove-Item 'C:\\Windows\\System32\\spool\\PRINTERS\\*' -Force; Start-Service 'Spooler' }}",
        "render_body": lambda ctx: (
            f"🖨️ **Automated IT Playbook Executed: Print Spooler Queue Purge & Service Cycle**\n\n"
            f"- **Target Host:** `{ctx['device_name']}` (`{ctx['ip_address']}`)\n"
            f"- **Service Name:** `Print Spooler (spoolsv.exe)`\n"
            f"- **Purged Queue Jobs:** `Cleaned locked spool files in C:\\Windows\\System32\\spool\\PRINTERS`\n"
            f"- **Service Status:** `RUNNING (Automatic)`\n\n"
            f"```powershell\n"
            f"PS C:\\> Stop-Service -Name 'Spooler' -Force\n"
            f"PS C:\\> Remove-Item 'C:\\Windows\\System32\\spool\\PRINTERS\\*' -Force\n"
            f"PS C:\\> Start-Service -Name 'Spooler'\n"
            f"Spooler status: RUNNING (PID: 4192)\n"
            f"```\n\n"
            f"Local printer queue is cleared. Please submit a new print job to test."
        ),
        "render_output": lambda ctx: (
            f"Connecting to remote service manager on {ctx['device_name']}...\n"
            f"[OK] Service 'Spooler' found (State: Running)\n"
            f"Stopping Spooler service...\n"
            f"  -> Service stopped\n"
            f"Clearing C:\\Windows\\System32\\spool\\PRINTERS\\*...\n"
            f"  -> Removed 2 stale spool files\n"
            f"Starting Spooler service...\n"
            f"  -> Service started successfully (PID: 4192)\n"
            f"Exit Code: 0 (Success)"
        ),
    },
}


# Playbooks and ping are demo simulations: nothing is executed on a real host.
# Every result says so, so nobody mistakes a canned success for a real fix.
SIMULATION_NOTICE = "\n\n> ⚠️ _Simulated playbook (demo environment) — no command was run on a real system._"


@router.post("/{ticket_id}/execute-playbook", response_model=schemas.PlaybookExecuteResponse)
async def execute_playbook(
    ticket_id: int,
    payload: schemas.PlaybookExecuteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*STAFF_ROLES)),
):
    """
    Execute an automated IT Quick-Fix Playbook (Technician Macro & Remote SOP).
    Simulates remote execution, appends structured markdown diagnostic log to the ticket thread,
    and logs an audit trail.
    """
    import secrets

    ticket = _get_ticket_or_404(ticket_id, db)

    playbook_def = PLAYBOOK_CATALOG.get(payload.playbook_id)
    if not playbook_def:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown playbook '{payload.playbook_id}'. Available: {list(PLAYBOOK_CATALOG.keys())}"
        )

    submitter = ticket.submitter
    device_name = (payload.target_device or ticket.device_name or DEFAULT_DEVICE["device_name"])[:128]
    ip_address = ticket.ip_address or DEFAULT_DEVICE["ip_address"]
    ctx = {
        "user_email": submitter.email if submitter else "user@company.com",
        "user_name": submitter.name if submitter else "End User",
        "device_name": device_name,
        "ip_address": ip_address,
        "temp_token": f"SIM-{secrets.token_hex(3).upper()}",
        "tech_name": current_user.name,
    }

    msg = models.TicketMessage(
        ticket_id=ticket.id,
        sender_type="technician",
        sender_id=current_user.id,
        body=playbook_def["render_body"](ctx) + SIMULATION_NOTICE,
    )
    db.add(msg)

    if ticket.status in ("assigned", "escalated", "new"):
        ticket.status = "in_progress"

    db.commit()
    db.refresh(msg)

    write_audit(db, current_user, "execute_it_playbook", "ticket", ticket.id,
                f"Executed (simulated) playbook '{playbook_def['title']}' on {device_name} ({ip_address}) for Ticket #{ticket.id}")

    return schemas.PlaybookExecuteResponse(
        playbook_id=payload.playbook_id,
        title=playbook_def["title"],
        status="success",
        execution_time_ms=secrets.randbelow(330) + 320,
        command_executed=playbook_def["cmd_pattern"].format(**ctx),
        command_output=playbook_def["render_output"](ctx),
        exit_code=0,
        technician_note=f"Playbook '{playbook_def['title']}' simulated successfully (demo mode).",
        message=msg,
    )


@router.post("/{ticket_id}/ping-device", response_model=schemas.PingDeviceResponse)
def ping_device(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*STAFF_ROLES)),
):
    """Simulated ICMP echo test to the workstation IP address (demo mode)."""
    ticket = _get_ticket_or_404(ticket_id, db)

    ip = ticket.ip_address or DEFAULT_DEVICE["ip_address"]
    device_name = ticket.device_name or DEFAULT_DEVICE["device_name"]

    raw_output = (
        f"[SIMULATED] Pinging {device_name} [{ip}] with 32 bytes of data:\n"
        f"Reply from {ip}: bytes=32 time=3.8ms TTL=126\n"
        f"Reply from {ip}: bytes=32 time=4.2ms TTL=126\n"
        f"Reply from {ip}: bytes=32 time=4.0ms TTL=126\n"
        f"Reply from {ip}: bytes=32 time=4.4ms TTL=126\n\n"
        f"Ping statistics for {ip}:\n"
        f"    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),\n"
        f"Approximate round trip times in milli-seconds:\n"
        f"    Minimum = 3.8ms, Maximum = 4.4ms, Average = 4.1ms"
    )

    return schemas.PingDeviceResponse(
        ip_address=ip,
        device_name=device_name,
        online=True,
        packets_sent=4,
        packets_received=4,
        avg_latency_ms=4.1,
        raw_output=raw_output,
    )
