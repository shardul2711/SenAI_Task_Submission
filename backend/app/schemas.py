from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

# --- Ingestion Schemas ---
class EmailIngestRequest(BaseModel):
    message_id: str
    sender: str
    subject: Optional[str] = None
    body: Optional[str] = None
    timestamp: str  # Can be ISO-8601 string
    thread_id: str

class EmailIngestResponse(BaseModel):
    job_id: str
    status: str
    message_id: str
    thread_id: str

# --- Entity Extraction Schemas ---
class DetectedEntities(BaseModel):
    order_ids: List[str] = Field(default_factory=list)
    ticket_ids: List[str] = Field(default_factory=list)
    monetary_amounts: List[str] = Field(default_factory=list)
    deadlines: List[str] = Field(default_factory=list)
    products_mentioned: List[str] = Field(default_factory=list)
    companies: List[str] = Field(default_factory=list)
    people: List[str] = Field(default_factory=list)

# --- Email & Action Schemas ---
class ActionSchema(BaseModel):
    id: int
    email_id: int
    action_type: str
    agent_reasoning_log: Optional[str] = None
    proposed_content: Optional[str] = None
    is_approved: bool
    approved_by: Optional[str] = None
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmailSchema(BaseModel):
    id: int
    thread_id: str
    message_id: str
    sender: str
    subject: str
    body: str
    timestamp: datetime
    sentiment_score: float
    category: Optional[str] = None
    urgency: str
    requires_human: bool
    confidence: float
    raw_entities: Optional[Dict[str, Any]] = None
    status: str
    actions: List[ActionSchema] = []

    class Config:
        from_attributes = True

class DraftUpdateSchema(BaseModel):
    proposed_content: str

# --- Thread Schema ---
class ThreadSchema(BaseModel):
    id: int
    thread_id: str
    subject: str
    sender_email: str
    first_seen_at: datetime
    last_updated_at: datetime
    status: str
    assigned_to: Optional[str] = None
    emails: List[EmailSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True

# --- Contact Schemas ---
class ContactSchema(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    status: str
    account_value: float
    churn_risk_score: float
    created_at: datetime
    last_contact_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ContactStatusUpdateSchema(BaseModel):
    status: str

# --- Audit Log Schema ---
class AuditLogSchema(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    action: str
    performed_by: str
    timestamp: datetime
    diff: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# --- Analytics Schemas ---
class DashboardStats(BaseModel):
    pending_count: int
    replied_count: int
    escalated_count: int
    critical_count: int
    spam_filtered_count: int

class SentimentPoint(BaseModel):
    date: str
    average_sentiment: float

class CategoryCount(BaseModel):
    category: str
    count: int

# --- RAG Schema ---
class RAGSearchResponse(BaseModel):
    id: str
    source_doc: str
    chunk: str
    score: float
