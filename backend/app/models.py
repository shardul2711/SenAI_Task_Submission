from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Numeric, ForeignKey, Enum, func, Index, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    status = Column(Enum("VIP", "Blocked", "Active", "Churned"), default="Active", nullable=False)
    account_value = Column(Numeric(12, 2), default=0.00, nullable=False)
    churn_risk_score = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_contact_at = Column(DateTime, nullable=True)

class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String(255), unique=True, nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    sender_email = Column(String(255), nullable=False, index=True)
    first_seen_at = Column(DateTime, nullable=False)
    last_updated_at = Column(DateTime, nullable=False, index=True)
    status = Column(Enum("Open", "Resolved", "Escalated", "Ignored"), default="Open", nullable=False)
    assigned_to = Column(String(255), nullable=True)

    emails = relationship("Email", back_populates="thread", cascade="all, delete-orphan", order_by="Email.timestamp.asc()")

class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String(255), ForeignKey("threads.thread_id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    sender = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    sentiment_score = Column(Float, default=0.0, nullable=False, index=True)
    category = Column(String(50), nullable=True, index=True)
    urgency = Column(Enum("Critical", "High", "Medium", "Low"), default="Low", nullable=False, index=True)
    requires_human = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    raw_entities = Column(JSON, nullable=True)
    status = Column(Enum("Received", "Processing", "Replied", "Escalated", "Ignored"), default="Received", nullable=False)

    thread = relationship("Thread", back_populates="emails")
    actions = relationship("Action", back_populates="email", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_email_created_at", "timestamp"),
    )

class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(Enum("Auto-Reply", "Escalate", "Legal-Flag", "Ticket-Created", "Ignored"), nullable=False)
    agent_reasoning_log = Column(Text, nullable=True)  # Will store JSON string or text log
    proposed_content = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(255), nullable=True)
    executed_at = Column(DateTime, nullable=True)

    email = relationship("Email", back_populates="actions")

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_doc = Column(String(255), nullable=False)
    chunk_text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

class WebIntelligenceCache(Base):
    __tablename__ = "web_intelligence_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_url = Column(String(500), nullable=False)
    target_entity = Column(String(255), nullable=False, index=True)
    scraped_data = Column(JSON, nullable=False)
    scraped_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)
    action = Column(String(255), nullable=False)
    performed_by = Column(String(255), nullable=False)  # 'agent' or user_id
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    diff = Column(JSON, nullable=True)
