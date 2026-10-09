import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from auth import require_role
import models, schemas

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=schemas.MetricsOut)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin", "technician")),
):
    total = db.query(models.Ticket).count()
    deflected = db.query(models.Ticket).filter(models.Ticket.status == "deflected").count()
    escalated = db.query(models.Ticket).filter(models.Ticket.status == "escalated").count()
    resolved = db.query(models.Ticket).filter(
        models.Ticket.status.in_(["resolved", "closed"])
    ).count()
    open_backlog = db.query(models.Ticket).filter(
        models.Ticket.status.in_(["new", "ai_handling", "escalated", "assigned", "in_progress"])
    ).count()

    now = datetime.utcnow()
    sla_breached = db.query(models.Ticket).filter(
        models.Ticket.sla_due < now,
        models.Ticket.status.in_(["new", "ai_handling", "escalated", "assigned", "in_progress"]),
    ).count()

    # Avg resolution hours
    resolved_tickets = db.query(models.Ticket).filter(
        models.Ticket.resolved_at.isnot(None)
    ).all()
    avg_hours = None
    if resolved_tickets:
        durations = [
            (t.resolved_at - t.created_at).total_seconds() / 3600
            for t in resolved_tickets
            if t.resolved_at and t.created_at
        ]
        avg_hours = sum(durations) / len(durations) if durations else None

    # By category
    cat_rows = db.query(models.Ticket.category, func.count()).group_by(models.Ticket.category).all()
    tickets_by_category = {r[0] or "unclassified": r[1] for r in cat_rows}

    # By priority
    pri_rows = db.query(models.Ticket.priority, func.count()).group_by(models.Ticket.priority).all()
    tickets_by_priority = {r[0] or "unset": r[1] for r in pri_rows}

    # By status
    stat_rows = db.query(models.Ticket.status, func.count()).group_by(models.Ticket.status).all()
    tickets_by_status = {r[0]: r[1] for r in stat_rows}

    # 7-day deflection rate
    seven_days_ago = now - timedelta(days=7)
    total_7d = db.query(models.Ticket).filter(models.Ticket.created_at >= seven_days_ago).count()
    defl_7d = db.query(models.Ticket).filter(
        models.Ticket.status == "deflected",
        models.Ticket.created_at >= seven_days_ago,
    ).count()
    defl_rate_7d = round((defl_7d / total_7d * 100), 1) if total_7d else 0.0

    return schemas.MetricsOut(
        total_tickets=total,
        deflected=deflected,
        deflection_rate=round((deflected / total * 100), 1) if total else 0.0,
        escalated=escalated,
        resolved=resolved,
        open_backlog=open_backlog,
        sla_breached=sla_breached,
        avg_resolution_hours=round(avg_hours, 2) if avg_hours is not None else None,
        tickets_by_category=tickets_by_category,
        tickets_by_priority=tickets_by_priority,
        tickets_by_status=tickets_by_status,
        recent_deflection_rate_7d=defl_rate_7d,
    )


@router.get("/audit-log", response_model=List[schemas.AuditLogOut])
def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    actor_type: Optional[str] = Query(None, description="user | technician | admin | ai"),
    action: Optional[str] = Query(None, description="exact action name, e.g. ticket_escalated"),
    q: Optional[str] = Query(None, max_length=200, description="search the detail text"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """Audit log entries, newest first — admin only. Filterable and paged."""
    query = db.query(models.AuditLog)
    if actor_type:
        query = query.filter(models.AuditLog.actor_type == actor_type)
    if action:
        query = query.filter(models.AuditLog.action == action)
    if q:
        query = query.filter(models.AuditLog.detail.icontains(q))
    entries = query.order_by(models.AuditLog.id.desc()).offset(offset).limit(limit).all()

    # Show who did it by name, not just an id
    actor_ids = {e.actor_id for e in entries if e.actor_id}
    names = dict(db.query(models.User.id, models.User.name).filter(models.User.id.in_(actor_ids)).all()) if actor_ids else {}
    return [schemas.AuditLogOut.model_validate(e).model_copy(update={"actor_name": names.get(e.actor_id)}) for e in entries]


@router.get("/audit-log/actions", response_model=List[str])
def get_audit_actions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    """Distinct action names, for the audit log filter."""
    return [row[0] for row in db.query(models.AuditLog.action).distinct().order_by(models.AuditLog.action).all()]


@router.get("/export")
def export_metrics_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin", "technician")),
):
    """Export operational ticket data, SLA outcomes, and performance metrics as CSV."""
    tickets = db.query(models.Ticket).order_by(models.Ticket.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Ticket ID",
        "Subject",
        "Category",
        "Priority",
        "Status",
        "Target Level",
        "Suggested Team",
        "Submitter Name",
        "Submitter Email",
        "Assignee Name",
        "Assignee Email",
        "Mood",
        "Language",
        "Created At (UTC)",
        "Resolved At (UTC)",
        "SLA Due (UTC)",
        "SLA Status",
        "Resolution Time (Minutes)",
        "Resolution Time (Hours)",
    ])

    now = datetime.utcnow()

    for t in tickets:
        # Calculate resolution time
        res_minutes = ""
        res_hours = ""
        if t.resolved_at and t.created_at:
            duration_secs = (t.resolved_at - t.created_at).total_seconds()
            res_minutes = round(duration_secs / 60.0, 1)
            res_hours = round(duration_secs / 3600.0, 2)

        # Determine SLA Status
        sla_status = "Not Set"
        if t.status in ("resolved", "closed", "deflected"):
            if t.sla_due and t.resolved_at:
                sla_status = "Breached" if t.resolved_at > t.sla_due else "Met"
            elif t.sla_due:
                sla_status = "Met"
        elif t.sla_due:
            sla_status = "Breached" if now > t.sla_due else "Active"

        writer.writerow([
            t.id,
            t.subject,
            t.category or "unclassified",
            t.priority or "unset",
            t.status,
            t.target_level or "L1",
            t.suggested_team or "",
            t.submitter.name if t.submitter else "",
            t.submitter.email if t.submitter else "",
            t.assignee.name if t.assignee else "Unassigned",
            t.assignee.email if t.assignee else "",
            t.mood or "neutral",
            t.language or "English",
            t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            t.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if t.resolved_at else "",
            t.sla_due.strftime("%Y-%m-%d %H:%M:%S") if t.sla_due else "",
            sla_status,
            res_minutes,
            res_hours,
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=nexusit_service_metrics.csv"
        },
    )

