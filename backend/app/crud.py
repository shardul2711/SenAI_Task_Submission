from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.models import Contact, Thread, Email, Action, AuditLog, KnowledgeChunk
from typing import Optional, List, Dict, Any

# --- Contact CRUD ---
def get_contact_by_email(db: Session, email: str) -> Optional[Contact]:
    return db.query(Contact).filter(Contact.email == email).first()

def create_contact(db: Session, email: str, name: str = None, company: str = None) -> Contact:
    db_contact = Contact(
        email=email,
        name=name or email.split("@")[0].title(),
        company=company or "Unknown",
        status="Active"
    )
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def update_contact_status(db: Session, email: str, status: str) -> Optional[Contact]:
    db_contact = get_contact_by_email(db, email)
    if not db_contact:
        return None
    
    old_status = db_contact.status
    db_contact.status = status
    db.commit()
    db.refresh(db_contact)
    
    # Write audit log
    create_audit_log(
        db,
        entity_type="contact",
        entity_id=email,
        action="update_status",
        performed_by="user",
        diff={"old_status": old_status, "new_status": status}
    )
    
    return db_contact

# --- Thread CRUD ---
def get_thread_by_id(db: Session, thread_id: str) -> Optional[Thread]:
    return db.query(Thread).filter(Thread.thread_id == thread_id).first()

def get_threads_by_contact_email(db: Session, email: str) -> List[Thread]:
    return db.query(Thread).filter(Thread.sender_email == email).all()

def create_thread(db: Session, thread_id: str, subject: str, sender_email: str) -> Thread:
    db_thread = Thread(
        thread_id=thread_id,
        subject=subject,
        sender_email=sender_email,
        first_seen_at=datetime.utcnow(),
        last_updated_at=datetime.utcnow(),
        status="Open"
    )
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread

# --- Email CRUD ---
def get_email_by_message_id(db: Session, message_id: str) -> Optional[Email]:
    return db.query(Email).filter(Email.message_id == message_id).first()

def get_emails_by_thread(db: Session, thread_id: str) -> List[Email]:
    return db.query(Email).filter(Email.thread_id == thread_id).order_by(Email.timestamp.asc()).all()

def create_email(db: Session, email_data: dict) -> Email:
    db_email = Email(
        thread_id=email_data["thread_id"],
        message_id=email_data["message_id"],
        sender=email_data["sender"],
        subject=email_data["subject"],
        body=email_data["body"],
        timestamp=email_data["timestamp"],
        sentiment_score=email_data.get("sentiment_score", 0.0),
        category=email_data.get("category"),
        urgency=email_data.get("urgency", "Low"),
        requires_human=email_data.get("requires_human", False),
        confidence=email_data.get("confidence", 1.0),
        raw_entities=email_data.get("raw_entities"),
        status=email_data.get("status", "Received")
    )
    db.add(db_email)
    
    # Update thread's last updated time
    db_thread = get_thread_by_id(db, email_data["thread_id"])
    if db_thread:
        db_thread.last_updated_at = email_data["timestamp"]
    
    db.commit()
    db.refresh(db_email)
    return db_email

# --- Action CRUD ---
def get_action_by_id(db: Session, action_id: int) -> Optional[Action]:
    return db.query(Action).filter(Action.id == action_id).first()

def get_actions_by_email(db: Session, email_id: int) -> List[Action]:
    return db.query(Action).filter(Action.email_id == email_id).all()

def create_action(db: Session, email_id: int, action_type: str, agent_reasoning_log: str, proposed_content: str = None) -> Action:
    db_action = Action(
        email_id=email_id,
        action_type=action_type,
        agent_reasoning_log=agent_reasoning_log,
        proposed_content=proposed_content,
        is_approved=False
    )
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action

def update_draft_content(db: Session, action_id: int, proposed_content: str) -> Optional[Action]:
    db_action = get_action_by_id(db, action_id)
    if not db_action:
        return None
    old_content = db_action.proposed_content
    db_action.proposed_content = proposed_content
    db.commit()
    db.refresh(db_action)
    
    create_audit_log(
        db,
        entity_type="action",
        entity_id=str(action_id),
        action="update_draft",
        performed_by="user",
        diff={"old_content": old_content, "new_content": proposed_content}
    )
    return db_action

def approve_action(db: Session, action_id: int, approved_by: str) -> Optional[Action]:
    db_action = get_action_by_id(db, action_id)
    if not db_action:
        return None
    
    db_action.is_approved = True
    db_action.approved_by = approved_by
    db_action.executed_at = datetime.utcnow()
    
    # Update corresponding email and thread status
    db_email = db_action.email
    if db_email:
        if db_action.action_type == "Auto-Reply":
            db_email.status = "Replied"
            if db_email.thread:
                db_email.thread.status = "Resolved"
        elif db_action.action_type == "Escalate":
            db_email.status = "Escalated"
            db_email.requires_human = True
            if db_email.thread:
                db_email.thread.status = "Escalated"
        elif db_action.action_type == "Legal-Flag":
            db_email.status = "Escalated"
            db_email.requires_human = True
            if db_email.thread:
                db_email.thread.status = "Escalated"
        elif db_action.action_type == "Ticket-Created":
            db_email.status = "Processing"
            
    db.commit()
    db.refresh(db_action)
    
    create_audit_log(
        db,
        entity_type="action",
        entity_id=str(action_id),
        action="approve_action",
        performed_by=approved_by,
        diff={"is_approved": True, "executed_at": str(db_action.executed_at)}
    )
    
    return db_action

# --- Audit Log CRUD ---
def create_audit_log(db: Session, entity_type: str, entity_id: str, action: str, performed_by: str, diff: dict = None) -> AuditLog:
    db_log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        performed_by=performed_by,
        diff=diff
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_audit_logs_for_entity(db: Session, entity_type: str, entity_id: str) -> List[AuditLog]:
    return db.query(AuditLog).filter(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id
    ).order_by(AuditLog.timestamp.desc()).all()

# --- Analytics Queries ---
def get_dashboard_stats(db: Session) -> Dict[str, int]:
    # Counts: Pending, Replied, Escalated, Critical, Spam filtered
    pending = db.query(Email).filter(Email.status == "Received", Email.requires_human == True).count()
    replied = db.query(Email).filter(Email.status == "Replied").count()
    escalated = db.query(Email).filter(Email.status == "Escalated").count()
    critical = db.query(Email).filter(Email.urgency == "Critical").count()
    spam = db.query(Email).filter(Email.category == "Spam").count()
    
    return {
        "pending_count": pending,
        "replied_count": replied,
        "escalated_count": escalated,
        "critical_count": critical,
        "spam_filtered_count": spam
    }

def get_sentiment_trend(db: Session, sender_email: Optional[str] = None, days: int = 30) -> List[Dict[str, Any]]:
    # Query emails in last N days
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    query = db.query(Email.timestamp, Email.sentiment_score)
    if sender_email:
        query = query.filter(Email.sender == sender_email)
    query = query.filter(Email.timestamp >= cutoff_date).order_by(Email.timestamp.asc())
    
    emails = query.all()
    
    # Group by date and calculate average sentiment
    daily_sentiment = {}
    for email_time, score in emails:
        date_str = email_time.strftime("%Y-%m-%d")
        if date_str not in daily_sentiment:
            daily_sentiment[date_str] = []
        daily_sentiment[date_str].append(score)
        
    trend = []
    for date_str, scores in daily_sentiment.items():
        trend.append({
            "date": date_str,
            "average_sentiment": round(sum(scores) / len(scores), 4)
        })
        
    return trend

def get_category_breakdown(db: Session) -> List[Dict[str, Any]]:
    results = db.query(Email.category, func.count(Email.id)).group_by(Email.category).all()
    return [{"category": cat or "Unclassified", "count": count} for cat, count in results]
