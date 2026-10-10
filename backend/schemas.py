"""
Pydantic schemas for request/response validation.
"""

import re
from datetime import datetime
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator

from config import settings

Role = Literal["enduser", "technician", "admin"]
SupportLevel = Literal["L1", "L2", "L3"]
TicketStatus = Literal["new", "ai_handling", "deflected", "escalated", "assigned", "in_progress", "resolved", "closed"]
Priority = Literal["low", "medium", "high", "critical"]
Category = Literal["hardware", "software", "network", "access", "account", "general", "other"]
Severity = Literal["critical", "warning", "info", "maintenance"]

_SAFE_URL = re.compile(r"^(data:[\w.+-]+/[\w.+-]+(;[\w=.+-]+)*,|https?://)", re.IGNORECASE)


def validate_attachments(value: Optional[List[Any]]) -> Optional[List[dict]]:
    """Attachments are stored inline as data URLs. Enforce count, size and
    URL scheme so a client cannot store javascript: links or huge blobs."""
    if value is None:
        return None
    if len(value) > settings.MAX_ATTACHMENTS:
        raise ValueError(f"At most {settings.MAX_ATTACHMENTS} attachments are allowed")
    max_chars = int(settings.MAX_ATTACHMENT_BYTES * 4 / 3) + 256  # base64 overhead
    cleaned = []
    for att in value:
        if not isinstance(att, dict):
            raise ValueError("Each attachment must be an object")
        name = str(att.get("name") or "attachment")[:255]
        for key in ("url", "data"):
            link = att.get(key)
            if link is None:
                continue
            if not isinstance(link, str) or not _SAFE_URL.match(link):
                raise ValueError(f"Attachment '{name}' has an unsupported URL scheme")
            if len(link) > max_chars:
                raise ValueError(f"Attachment '{name}' exceeds the size limit")
        cleaned.append({**att, "name": name})
    return cleaned


KB_CATEGORY_ALIASES = {"vpn": "network", "wifi": "network", "wi-fi": "network", "account": "access",
                       "accounts": "access", "passwords": "access", "access & passwords": "access"}
KB_CATEGORIES = {"network", "access", "hardware", "software", "general", "other"}


def normalize_kb_category(value: Optional[str]) -> Optional[str]:
    """KB categories must match what the chatbot and filters expect (lowercase)."""
    if value is None:
        return None
    value = KB_CATEGORY_ALIASES.get(value.strip().lower(), value.strip().lower())
    return value if value in KB_CATEGORIES else "other"


# ─────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = "enduser"
    team: Optional[str] = Field(None, max_length=64)
    support_level: Optional[SupportLevel] = None
    primary_device: Optional[Any] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ResetLinkOut(BaseModel):
    reset_path: str
    expires_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    team: Optional[str] = None
    support_level: Optional[str] = "L1"
    primary_device: Optional[Any] = None
    created_at: datetime
    password_reset_requested_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    role: Optional[Role] = None
    team: Optional[str] = Field(None, max_length=64)
    support_level: Optional[SupportLevel] = None
    primary_device: Optional[Any] = None


# ─────────────────────────────────────────────────────────────────
# Tickets
# ─────────────────────────────────────────────────────────────────
class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=20000)
    attachments: Optional[List[Any]] = None

    _check_attachments = field_validator("attachments")(validate_attachments)
    device_name: Optional[str] = None
    device_os: Optional[str] = None
    ip_address: Optional[str] = None
    subnet_vlan: Optional[str] = None
    mac_address: Optional[str] = None
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    last_reboot: Optional[str] = None
    edr_status: Optional[str] = None
    hardware_specs: Optional[str] = None
    domain_join: Optional[str] = None
    office_location: Optional[str] = None


class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    assigned_to: Optional[int] = None
    priority: Optional[Priority] = None
    category: Optional[Category] = None


class TicketStatusUpdate(BaseModel):
    # "ai_deflected" is a legacy alias the UI may still send for "deflected"
    status: Optional[Literal["new", "ai_handling", "deflected", "ai_deflected", "escalated",
                             "assigned", "in_progress", "resolved", "closed"]] = None
    assigned_to: Optional[int] = None


class MessageOut(BaseModel):
    id: int
    ticket_id: int
    sender_type: str
    sender_id: Optional[int] = None
    body: str
    attachments: Optional[List[Any]] = None
    created_at: datetime
    sender: Optional[UserOut] = None

    class Config:
        from_attributes = True


class HandoverBriefingOut(BaseModel):
    id: int
    ticket_id: int
    summary: str
    user_tried: Optional[str] = None
    ai_tried: Optional[str] = None
    likely_causes: Optional[List[str]] = None
    suggested_steps: Optional[List[str]] = None
    related_ticket_ids: Optional[List[str]] = None
    generated_at: datetime

    class Config:
        from_attributes = True


class TicketRatingCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)


class TicketRatingOut(BaseModel):
    id: int
    ticket_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: int
    user_id: int
    subject: str
    description: str
    category: Optional[str] = None
    priority: Optional[str] = None
    mood: Optional[str] = None
    language: Optional[str] = None
    status: str
    assigned_to: Optional[int] = None
    target_level: Optional[str] = "L1"
    suggested_team: Optional[str] = None
    tags: Optional[List[str]] = None
    attachments: Optional[List[Any]] = None
    
    # ── Enterprise Device & Asset Context ──────────────────────
    device_name: Optional[str] = None
    device_os: Optional[str] = None
    ip_address: Optional[str] = None
    subnet_vlan: Optional[str] = None
    mac_address: Optional[str] = None
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    last_reboot: Optional[str] = None
    edr_status: Optional[str] = None
    hardware_specs: Optional[str] = None
    domain_join: Optional[str] = None
    office_location: Optional[str] = None

    sla_due: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    submitter: Optional[UserOut] = None
    assignee: Optional[UserOut] = None
    messages: List[MessageOut] = []
    briefing: Optional[HandoverBriefingOut] = None
    rating: Optional[TicketRatingOut] = None

    class Config:
        from_attributes = True


class TicketListItem(BaseModel):
    id: int
    subject: str
    category: Optional[str] = None
    priority: Optional[str] = None
    mood: Optional[str] = None
    status: str
    assigned_to: Optional[int] = None
    target_level: Optional[str] = "L1"
    suggested_team: Optional[str] = None
    tags: Optional[List[str]] = None
    attachments: Optional[List[Any]] = None
    device_name: Optional[str] = None
    device_os: Optional[str] = None
    ip_address: Optional[str] = None
    asset_tag: Optional[str] = None
    sla_due: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    submitter: Optional[UserOut] = None
    assignee: Optional[UserOut] = None

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    attachments: Optional[List[Any]] = None

    _check_attachments = field_validator("attachments")(validate_attachments)


# ─────────────────────────────────────────────────────────────────
# Technician Playbooks & Remediation
# ─────────────────────────────────────────────────────────────────
class PlaybookExecuteRequest(BaseModel):
    playbook_id: str
    target_device: Optional[str] = None
    custom_params: Optional[dict] = None


class PlaybookExecuteResponse(BaseModel):
    playbook_id: str
    title: str
    status: str
    execution_time_ms: int
    command_executed: str
    command_output: str
    exit_code: int
    technician_note: str
    message: MessageOut


class PingDeviceResponse(BaseModel):
    ip_address: str
    device_name: str
    online: bool
    packets_sent: int = 4
    packets_received: int = 4
    avg_latency_ms: float = 4.2
    raw_output: str


# ─────────────────────────────────────────────────────────────────
# Knowledge Base
# ─────────────────────────────────────────────────────────────────
class KBArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1)
    tags: Optional[str] = None
    category: Optional[str] = None

    _check_category = field_validator("category")(normalize_kb_category)


class KBArticleUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    status: Optional[Literal["published", "pending_approval"]] = None

    _check_category = field_validator("category")(normalize_kb_category)


class KBFeedback(BaseModel):
    helpful: bool


class KBArticleOut(BaseModel):
    id: int
    title: str
    body: str
    tags: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    source_ticket_id: Optional[int] = None
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────
# Major Incident Management & System Announcements
# ─────────────────────────────────────────────────────────────────
class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    message: str = Field(min_length=1)
    severity: Severity = "warning"
    affected_services: Optional[List[str]] = None
    workaround: Optional[str] = None
    estimated_resolution: Optional[str] = None
    is_active: bool = True


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    message: Optional[str] = None
    severity: Optional[Severity] = None
    affected_services: Optional[List[str]] = None
    workaround: Optional[str] = None
    estimated_resolution: Optional[str] = None
    is_active: Optional[bool] = None


class AnnouncementOut(BaseModel):
    id: int
    title: str
    message: str
    severity: str
    is_active: bool
    affected_services: Optional[List[str]] = None
    workaround: Optional[str] = None
    started_at: Optional[datetime] = None
    estimated_resolution: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    author: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────
class MetricsOut(BaseModel):
    total_tickets: int
    deflected: int
    deflection_rate: float
    escalated: int
    resolved: int
    open_backlog: int
    sla_breached: int
    avg_resolution_hours: Optional[float] = None
    tickets_by_category: dict
    tickets_by_priority: dict
    tickets_by_status: dict
    recent_deflection_rate_7d: float


# ─────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────
class AuditLogOut(BaseModel):
    id: int
    actor_type: str
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    detail: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────
# AI Diagnose Chatbot & Conversational Triage
# ─────────────────────────────────────────────────────────────────
class AIDiagnoseRequest(BaseModel):
    message: str
    chat_history: Optional[List[dict]] = []
    device_name: Optional[str] = None
    category: Optional[str] = None

class AIDiagnoseResponse(BaseModel):
    solution: str
    category: str
    priority: str
    can_resolve: bool
    confidence: Optional[str] = "high"
    used_articles: Optional[List[dict]] = []

class AITriageChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    chat_history: Optional[List[dict]] = []
    device_name: Optional[str] = None
    office_location: Optional[str] = None

class AITriageChatResponse(BaseModel):
    reply: str
    subject: str
    category: str
    priority: str
    status_intent: str  # "troubleshoot", "resolved", "escalate"
    can_resolve: bool
    used_articles: Optional[List[dict]] = []

class AITriageResolveRequest(BaseModel):
    subject: Optional[str] = None
    category: Optional[str] = "general"
    priority: Optional[str] = "low"
    messages: List[dict] = Field(max_length=100)
    device_name: Optional[str] = None
    office_location: Optional[str] = None
    used_article_ids: List[int] = Field(default_factory=list, max_length=20)

class AITriageEscalateRequest(BaseModel):
    subject: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    messages: List[dict] = Field(max_length=100)
    device_name: Optional[str] = None
    office_location: Optional[str] = None
    used_article_ids: List[int] = Field(default_factory=list, max_length=20)


# ─────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────
class NotificationOut(BaseModel):
    id: int
    kind: str
    message: str
    link: Optional[str] = None
    ticket_id: Optional[int] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationList(BaseModel):
    unread: int
    items: List[NotificationOut]
