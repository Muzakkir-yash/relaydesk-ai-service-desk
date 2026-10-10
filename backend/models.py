from datetime import datetime
import json
from sqlalchemy import (Column, Integer, String, Text, DateTime, Enum, ForeignKey, JSON, Boolean)
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(256), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum("enduser", "technician", "admin"), nullable=False, default="enduser")
    team = Column(String(64), nullable=True)
    support_level = Column(String(16), nullable=False, default="L1")  # "L1", "L2", "L3"
    primary_device = Column(JSON, nullable=True)  # Default enterprise endpoint assigned to user
    # Sessions issued before this moment are rejected (set when the password changes)
    password_changed_at = Column(DateTime, nullable=True)
    # Set by "Forgot password?"; cleared when an admin issues a reset link
    password_reset_requested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_tickets = relationship("Ticket", foreign_keys="Ticket.user_id", back_populates="submitter")
    assigned_tickets = relationship("Ticket", foreign_keys="Ticket.assigned_to", back_populates="assignee")
    messages = relationship("TicketMessage", back_populates="sender")

class PasswordResetToken(Base):
    """Single-use, 24-hour password reset link issued by an admin.
    Only a SHA-256 hash of the token is stored, never the token itself."""
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    """In-app notification shown under the bell icon."""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    kind = Column(String(32), nullable=False)       # e.g. ticket_assigned, reply, resolved
    message = Column(String(300), nullable=False)
    link = Column(String(200), nullable=True)       # page to open when clicked
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class ProblemCluster(Base):
    __tablename__ = "problem_clusters"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    likely_cause = Column(Text, nullable=True)
    ticket_ids = Column(JSON, nullable=True)
    status = Column(Enum("open", "acknowledged", "resolved"), nullable=False, default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tickets = relationship("Ticket", back_populates="cluster", foreign_keys="Ticket.cluster_id")

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum("hardware", "software", "network", "access", "account", "general", "other"), nullable=True)
    priority = Column(Enum("low", "medium", "high", "critical"), nullable=True)
    mood = Column(Enum("calm", "neutral", "frustrated"), nullable=True)
    language = Column(String(64), nullable=True)
    status = Column(Enum("new", "ai_handling", "deflected", "escalated", "assigned", "in_progress", "resolved", "closed"), nullable=False, default="new", index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    target_level = Column(String(16), nullable=True)  # "L1", "L2", "L3"
    suggested_team = Column(String(64), nullable=True)
    tags = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    
    # ── Enterprise Device & Asset Context ──────────────────────
    device_name = Column(String(128), nullable=True)       # e.g., CORP-LAPTOP-W11-842
    device_os = Column(String(128), nullable=True)         # e.g., Windows 11 Enterprise (Build 23H2)
    ip_address = Column(String(64), nullable=True)         # e.g., 10.14.88.24
    subnet_vlan = Column(String(128), nullable=True)       # e.g., VLAN 20 (HQ Floor 3 - Engineering)
    mac_address = Column(String(64), nullable=True)        # e.g., 00:1A:2B:3C:4D:5E
    asset_tag = Column(String(64), nullable=True)          # e.g., AST-84291
    serial_number = Column(String(64), nullable=True)      # e.g., PF39X8K2 / C02GL412MD6R
    last_reboot = Column(String(128), nullable=True)       # e.g., 3 days ago (Uptime: 74h 12m)
    edr_status = Column(String(128), nullable=True)        # e.g., CrowdStrike Falcon (Healthy / v7.14.0)
    hardware_specs = Column(String(256), nullable=True)    # e.g., Intel i7-1370P | 32 GB RAM | 512 GB NVMe
    domain_join = Column(String(128), nullable=True)       # e.g., CORP.INTERNAL (Hybrid / Intune Compliant)
    office_location = Column(String(128), nullable=True)   # e.g., HQ - Building B - Desk 304

    sla_due = Column(DateTime, nullable=True)
    cluster_id = Column(Integer, ForeignKey("problem_clusters.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    submitter = relationship("User", foreign_keys=[user_id], back_populates="submitted_tickets")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_tickets")
    messages = relationship("TicketMessage", back_populates="ticket", order_by="TicketMessage.created_at")
    briefing = relationship("HandoverBriefing", back_populates="ticket", uselist=False)
    ai_actions = relationship("AIAction", back_populates="ticket")
    rating = relationship("TicketRating", back_populates="ticket", uselist=False)
    cluster = relationship("ProblemCluster", back_populates="tickets", foreign_keys=[cluster_id])

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    sender_type = Column(Enum("user", "ai", "technician"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    attachments = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="messages")
    sender = relationship("User", back_populates="messages")

class KBArticle(Base):
    __tablename__ = "kb_articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    body = Column(Text, nullable=False)
    tags = Column(String(512), nullable=True)
    category = Column(String(64), nullable=True)
    source = Column(Enum("manual", "ai_drafted"), nullable=False, default="manual")
    status = Column(Enum("published", "pending_approval"), nullable=False, default="published")
    source_ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    # Self-service outcomes after the chatbot suggested this article (ranking feedback)
    helpful_count = Column(Integer, nullable=False, default=0, server_default="0")
    not_helpful_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HandoverBriefing(Base):
    __tablename__ = "handover_briefings"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True, nullable=False)
    summary = Column(Text, nullable=False)
    user_tried = Column(Text, nullable=True)
    ai_tried = Column(Text, nullable=True)
    likely_causes = Column(JSON, nullable=True)
    suggested_steps = Column(JSON, nullable=True)
    related_ticket_ids = Column(JSON, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="briefing")

class AIAction(Base):
    __tablename__ = "ai_actions"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    action_type = Column(Enum("classify", "deflect_attempt", "handover", "kb_draft", "cluster_detect"), nullable=False)
    input_snapshot = Column(Text, nullable=True)
    output_snapshot = Column(Text, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="ai_actions")

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    actor_type = Column(Enum("user", "technician", "admin", "ai"), nullable=False)
    actor_id = Column(Integer, nullable=True)
    action = Column(String(128), nullable=False)
    target_type = Column(String(64), nullable=True)
    target_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Enum("low", "medium", "high", "critical"), unique=True, nullable=False)
    response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)

class TicketRating(Base):
    __tablename__ = "ticket_ratings"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True, nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="rating")

# ── Major Incident Management & Global Outage Banner ───────────────
class SystemAnnouncement(Base):
    __tablename__ = "system_announcements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(Enum("critical", "warning", "info", "maintenance"), nullable=False, default="warning")
    is_active = Column(Boolean, default=True, nullable=False)
    affected_services = Column(JSON, nullable=True)       # e.g., ["GlobalProtect VPN", "EMEA Gateway"]
    workaround = Column(Text, nullable=True)             # e.g., "Switch to US-East-Failover in VPN settings"
    started_at = Column(DateTime, default=datetime.utcnow)
    estimated_resolution = Column(String(128), nullable=True) # e.g., "11:45 AM EST (In 30 mins)"
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author = relationship("User")

