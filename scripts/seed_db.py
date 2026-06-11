import sys
import os
import json
from datetime import datetime

# Adjust sys.path to resolve backend imports
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root_dir, "backend"))

from app.database import engine, Base, SessionLocal
from app.models import Contact, Thread, Email, Action, KnowledgeChunk, AuditLog
from app.services.rag import rag_service

def clear_database(db):
    print("Clearing existing database tables...")
    db.query(Action).delete()
    db.query(Email).delete()
    db.query(Thread).delete()
    db.query(Contact).delete()
    db.query(KnowledgeChunk).delete()
    db.query(AuditLog).delete()
    db.commit()

def seed_contacts(db):
    print("Seeding CRM contacts...")
    contacts = [
        Contact(
            email="alice.smith@greenlight-npo.org",
            name="Alice Smith",
            company="Greenlight NPO",
            status="Active",
            account_value=1188.00,  # $99/mo standard plan
            churn_risk_score=0.05
        ),
        Contact(
            email="bob.jones@enterprise.net",
            name="Bob Jones",
            company="Enterprise Net",
            status="VIP",
            account_value=85000.00,  # Enterprise high value
            churn_risk_score=0.45  # High risk due to outage & legal threat
        ),
        Contact(
            email="karen.w@retail-co.com",
            name="Karen W.",
            company="Retail Co",
            status="Active",
            account_value=3588.00,  # Pro plan
            churn_risk_score=0.95  # Churn threat!
        ),
        Contact(
            email="marcus.del@fintech-startup.co",
            name="Marcus Del",
            company="Fintech Startup",
            status="Active",
            account_value=12500.00,
            churn_risk_score=0.10
        ),
        Contact(
            email="charlie@fastlane-startup.com",
            name="Charlie",
            company="Fastlane Startup",
            status="Active",
            account_value=3588.00,
            churn_risk_score=0.15
        ),
        Contact(
            email="eleanor.voss@healthcare-group.org",
            name="Eleanor Voss",
            company="Healthcare Group",
            status="Active",
            account_value=23760.00,  # Prospect / 200 seats potential
            churn_risk_score=0.20
        ),
        Contact(
            email="nadia.k@global-logistics.com",
            name="Nadia K.",
            company="Global Logistics",
            status="VIP",
            account_value=45000.00,
            churn_risk_score=0.30
        ),
        Contact(
            email="user.confused@hotmail.com",
            name="Confused User",
            company="Individual",
            status="Active",
            account_value=99.00,
            churn_risk_score=0.50
        ),
        Contact(
            email="student@mit.edu",
            name="MIT Student",
            company="MIT",
            status="Active",
            account_value=0.00,
            churn_risk_score=0.10
        ),
        Contact(
            email="angry.user@domain.com",
            name="Angry User",
            company="Domain Corp",
            status="Active",
            account_value=299.00,
            churn_risk_score=0.99
        )
    ]
    
    for contact in contacts:
        db.add(contact)
    db.commit()
    print(f"Successfully seeded {len(contacts)} contacts.")

def seed_emails(db):
    print("Seeding emails from dataset...")
    dataset_path = os.path.join(root_dir, "documents", "68da89af-0a56-490d-93ac-f180673b26c9.json")
    if not os.path.exists(dataset_path):
        print(f"Dataset path {dataset_path} not found.")
        return
        
    with open(dataset_path, "r", encoding="utf-8") as f:
        emails_data = json.load(f)
        
    from app.services.heuristic import analyze_heuristics
    from app.services.llm import analyze_with_llm
    from app.services.agent import crm_agent
    import app.crud as crud
    
    success_count = 0
    for idx, item in enumerate(emails_data):
        sender = item["sender"]
        thread_id = item["thread_id"]
        message_id = item["message_id"]
        subject = item.get("subject") or "(No Subject)"
        body = item.get("body") or ""
        
        try:
            timestamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        except Exception:
            timestamp = datetime.utcnow()

        # Step 1: Run Layer 1 Heuristics
        heuristic_res = analyze_heuristics(sender, subject, body)
        cleaned_body = heuristic_res["cleaned_body"]
        if len(cleaned_body) > 10000:
            cleaned_body = cleaned_body[:10000] + "\n... [TRUNCATED]"

        # Step 2: Thread linking
        db_thread = crud.get_thread_by_id(db, thread_id)
        if not db_thread:
            db_thread = Thread(
                thread_id=thread_id,
                subject=subject,
                sender_email=sender,
                first_seen_at=timestamp,
                last_updated_at=timestamp,
                status="Open"
            )
            db.add(db_thread)
            db.commit()
            db.refresh(db_thread)

        # Step 3: Contact checking
        db_contact = crud.get_contact_by_email(db, sender)
        if not db_contact:
            db_contact = crud.create_contact(db, sender)

        # Step 4: RAG
        rag_chunks = rag_service.search(cleaned_body, top_k=3)

        # Step 5: LLM classification
        if heuristic_res["is_spam"]:
            category = "Spam"
            sentiment_score = -0.5
            urgency = "Low"
            requires_human = False
            entities = {}
            confidence = 1.0
        elif heuristic_res["is_internal"]:
            category = "Internal"
            sentiment_score = 0.0
            urgency = "Low"
            requires_human = False
            entities = {}
            confidence = 1.0
        else:
            llm_res = analyze_with_llm(
                email_body=cleaned_body,
                thread_history=[{"sender": sender, "body": cleaned_body}],
                rag_chunks=rag_chunks,
                message_id=message_id
            )
            category = llm_res.category
            sentiment_score = llm_res.sentiment_score
            urgency = llm_res.urgency if heuristic_res["urgency"] != "Critical" else "Critical"
            requires_human = llm_res.requires_human
            entities = llm_res.detected_entities.model_dump()
            confidence = llm_res.confidence

        # Step 6: Create Email Record in DB
        db_email = crud.create_email(db, {
            "thread_id": thread_id,
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "body": cleaned_body,
            "timestamp": timestamp,
            "sentiment_score": sentiment_score,
            "category": category,
            "urgency": urgency,
            "requires_human": requires_human,
            "confidence": confidence,
            "raw_entities": entities,
            "status": "Received"
        })

        db_contact.last_contact_at = timestamp
        db.commit()

        # Step 7: Sentiment Deterioration Check
        emails = crud.get_emails_by_thread(db, thread_id)
        negative_count = 0
        for e in reversed(emails):
            if e.sentiment_score < -0.3:
                negative_count += 1
            else:
                break
        if negative_count >= 3:
            db_email.requires_human = True
            db_email.status = "Escalated"
            db_thread.status = "Escalated"
            db.commit()
            
            crud.create_action(
                db=db,
                email_id=db_email.id,
                action_type="Escalate",
                agent_reasoning_log="Auto-escalated: Sentiment deterioration (3 consecutive negative emails).",
                proposed_content="System notice: Customer sentiment deteriorated."
            )

        # Step 8: Run Agent Loop
        if category == "Spam":
            db_email.status = "Ignored"
            db_thread.status = "Ignored"
            db.commit()
            crud.create_action(
                db=db,
                email_id=db_email.id,
                action_type="Ignored",
                agent_reasoning_log="Layer 1: Marked as spam by Heuristics engine.",
                proposed_content=None
            )
        elif category == "Internal":
            pass
        else:
            crm_agent.run_agent(
                email_id=db_email.id,
                message_id=message_id,
                body=cleaned_body,
                sender=sender,
                thread_id=thread_id,
                urgency=urgency,
                category=category,
                dry_run=False
            )
            
        success_count += 1
        
    print(f"Successfully processed and seeded {success_count} emails.")

def main():
    import pymysql
    from app.config import settings
    
    print("Ensuring MySQL database exists...")
    conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.MYSQL_DATABASE}")
        conn.commit()
        print(f"Database '{settings.MYSQL_DATABASE}' is ready.")
    except Exception as e:
        print(f"Error creating database: {e}")
    finally:
        conn.close()

    print("Initializing Database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Clear existing data to prevent primary key collisions/duplicates during re-runs
        clear_database(db)
        
        # Seed Contacts
        seed_contacts(db)
        
        # Seed Knowledge Base into ChromaDB and MySQL
        kb_path = os.path.join(root_dir, "knowledge_base")
        print(f"Seeding knowledge base from path: {kb_path}")
        rag_service.seed_knowledge_base(kb_path, db)
        
        # Seed Emails and Run Pipeline
        seed_emails(db)
        
        print("Database seeding completed successfully.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
