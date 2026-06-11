import os
import sys
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Resolve imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import Base, get_db
from app.services.heuristic import analyze_heuristics, clean_body
from app.services.llm import analyze_with_llm, get_mock_llm_result
from app.services.rag import rag_service
from app.services.agent import crm_agent
from app.auth import get_current_user, get_password_hash
import app.crud as crud
import app.models as models

# --- SQLite Test Database Setup ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override current admin dependency to bypass actual JWT validation in API testing
def override_get_current_user():
    return {"username": "admin", "role": "admin"}

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

@pytest.fixture(autouse=True, scope="function")
def setup_db():
    Base.metadata.create_all(bind=engine)
    # Seed default contacts
    db = TestingSessionLocal()
    crud.create_contact(db, "alice.smith@greenlight-npo.org", "Alice Smith", "Greenlight NPO")
    crud.create_contact(db, "bob.jones@enterprise.net", "Bob Jones", "Enterprise Net")
    crud.create_contact(db, "karen.w@retail-co.com", "Karen W.", "Retail Co")
    crud.create_contact(db, "marcus.del@fintech-startup.co", "Marcus Del", "Fintech Startup")
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

# --- Heuristics Layer 1 Tests ---
def test_heuristics_spam():
    res = analyze_heuristics("spam.bot@marketing-guru.io", "Boost your SEO by 300%", "Click here to claim your share of cash.")
    assert res["is_spam"] is True
    assert res["urgency"] == "Low"

def test_heuristics_security():
    res = analyze_heuristics("hacker@anon-collective.net", "Pay Now", "We have exfiltrated your database. Send 2 BTC to our wallet.")
    assert res["is_security"] is True
    assert res["urgency"] == "Critical"

def test_heuristics_internal():
    res = analyze_heuristics("hr@internal.com", "Holiday Party Reminder", "Party is Friday at 5 PM in main hall.")
    assert res["is_internal"] is True
    assert res["is_spam"] is False

def test_heuristics_clean_body():
    html_body = "<p>Hello <b>World</b>! &nbsp; Welcome.</p>"
    clean = clean_body(html_body)
    assert clean == "Hello World! Welcome."

# --- RAG Vector Search Tests ---
def test_rag_seeding():
    db = TestingSessionLocal()
    # Seed mock markdown file
    kb_dir = "test_knowledge"
    os.makedirs(kb_dir, exist_ok=True)
    with open(os.path.join(kb_dir, "test_policy.md"), "w", encoding="utf-8") as f:
        f.write("# Refund Policy\n\nNo refunds are allowed after 14 days under standard terms.")
    
    rag_service.seed_knowledge_base(kb_dir, db)
    
    # Verify vector search
    search_res = rag_service.search("refund window")
    assert len(search_res) > 0
    assert "Refund Policy" in search_res[0]["chunk"]
    
    # Cleanup files
    os.remove(os.path.join(kb_dir, "test_policy.md"))
    os.rmdir(kb_dir)
    db.close()

# --- LLM Classifier Tests ---
def test_llm_mock_gdpr():
    res = analyze_with_llm("Under GDPR Article 20, export my data.", message_id="msg_052")
    assert res.category == "Legal"
    assert res.urgency == "High"
    assert res.requires_human is True
    assert "GDPR Article 20" in res.suggested_reply

def test_llm_mock_ransomware():
    res = analyze_with_llm("Send 2 BTC or we publish your data.", message_id="msg_038")
    assert res.category == "Legal"
    assert res.urgency == "Critical"
    assert res.requires_human is True
    assert res.suggested_reply is None

# --- Ingestion API Tests ---
def test_ingestion_api():
    payload = {
        "message_id": "msg_test_01",
        "sender": "charlie@fastlane-startup.com",
        "subject": "Integration issue",
        "body": "Keep hitting 403 on events.",
        "timestamp": "2023-10-01T10:00:00Z",
        "thread_id": "thread_charlie_api"
    }
    response = client.post("/api/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["message_id"] == "msg_test_01"
    assert data["status"] == "processing"

# --- End-to-End Special Scenario Tests ---

def test_scenario_gdpr_right_to_portability():
    # msg_052 GDPR Right to Portability Request
    payload = {
        "message_id": "msg_052",
        "sender": "marcus.del@fintech-startup.co",
        "subject": "Data Export: GDPR Right to Portability Request",
        "body": "Under GDPR Article 20, I am formally requesting a complete export of all personal data...",
        "timestamp": "2023-10-17T08:00:00Z",
        "thread_id": "thread_gdpr_001"
    }
    # Direct Ingestion
    response = client.post("/api/ingest", json=payload)
    assert response.status_code == 200
    
    # Process background tasks synchronously
    db = TestingSessionLocal()
    # Trigger autonomous agent manually for testing scenario
    db_email = models.Email(
        thread_id="thread_gdpr_001",
        message_id="msg_052",
        sender="marcus.del@fintech-startup.co",
        subject="Data Export: GDPR Right to Portability Request",
        body="Under GDPR Article 20, I am formally requesting a complete export...",
        timestamp=datetime.utcnow(),
        category="Legal",
        urgency="High",
        requires_human=True,
        confidence=0.95,
        status="Received"
    )
    db.add(db_email)
    db.commit()
    
    # Run Agent
    res = crm_agent.run_agent(
        email_id=db_email.id,
        message_id="msg_052",
        body=db_email.body,
        sender=db_email.sender,
        thread_id=db_email.thread_id,
        urgency="High",
        category="Legal",
        dry_run=True  # Dry run to verify planning and tool usage
    )
    
    assert res["action_type"] == "Escalate"
    assert res["is_escalated"] is True
    assert "GDPR Article 20" in res["reply_draft"]
    db.close()

def test_scenario_ransomware_threat():
    # msg_038 Ransomware Threat
    db = TestingSessionLocal()
    db_email = models.Email(
        thread_id="thread_security_002",
        message_id="msg_038",
        sender="hacker@anon-collective.net",
        subject="We have your data - Pay Now",
        body="We have exfiltrated 50,000 customer records. Send 2 BTC or we publish the data.",
        timestamp=datetime.utcnow(),
        category="Legal",
        urgency="Critical",
        requires_human=True,
        confidence=0.99,
        status="Received"
    )
    db.add(db_email)
    db.commit()
    
    # Run Agent
    res = crm_agent.run_agent(
        email_id=db_email.id,
        message_id="msg_038",
        body=db_email.body,
        sender=db_email.sender,
        thread_id=db_email.thread_id,
        urgency="Critical",
        category="Legal",
        dry_run=True
    )
    
    assert res["action_type"] == "Legal-Flag" or res["action_type"] == "Escalate"
    assert res["is_escalated"] is True
    assert res["reply_draft"] is None or "never auto-reply" in str(res["reply_draft"]).lower() or len(str(res["reply_draft"])) < 5
    db.close()

def test_scenario_bob_outage_sla():
    # msg_060 Bob jones Outage SLA Breach
    db = TestingSessionLocal()
    db_email = models.Email(
        thread_id="thread_bob_outage",
        message_id="msg_060",
        sender="bob.jones@enterprise.net",
        subject="Escalation: SLA Breach + Legal Review",
        body="We have reviewed the incident report. The RCA is inadequate. Our legal team is now involved. Renewal on hold.",
        timestamp=datetime.utcnow(),
        category="Legal",
        urgency="Critical",
        requires_human=True,
        confidence=0.95,
        status="Received"
    )
    db.add(db_email)
    db.commit()
    
    res = crm_agent.run_agent(
        email_id=db_email.id,
        message_id="msg_060",
        body=db_email.body,
        sender=db_email.sender,
        thread_id=db_email.thread_id,
        urgency="Critical",
        category="Legal",
        dry_run=True
    )
    
    assert res["is_escalated"] is True
    assert "RCA" in res["reply_draft"] or "SLA" in res["reply_draft"]
    db.close()

def test_scenario_karen_refund_churn():
    # msg_033 Karen refund request
    db = TestingSessionLocal()
    db_email = models.Email(
        thread_id="thread_karen_refund",
        message_id="msg_033",
        sender="karen.w@retail-co.com",
        subject="Final Warning Before Public Review",
        body="I have now sent 3 emails. I am cancelling my subscription and leaving negative G2/Trustpilot reviews.",
        timestamp=datetime.utcnow(),
        category="Complaint",
        urgency="Critical",
        requires_human=True,
        confidence=0.90,
        status="Received"
    )
    db.add(db_email)
    db.commit()
    
    res = crm_agent.run_agent(
        email_id=db_email.id,
        message_id="msg_033",
        body=db_email.body,
        sender=db_email.sender,
        thread_id=db_email.thread_id,
        urgency="Critical",
        category="Complaint",
        dry_run=True
    )
    
    assert res["is_escalated"] is True
    assert "refund policy" in res["reply_draft"].lower() or "retention" in res["reply_draft"].lower() or "discount" in res["reply_draft"].lower() or "apologize" in res["reply_draft"].lower()
    db.close()

def test_scenario_alice_pricing_discount():
    # msg_041 Alice pro-rata upgrade mid-cycle
    db = TestingSessionLocal()
    db_email = models.Email(
        thread_id="thread_alice_pricing",
        message_id="msg_041",
        sender="alice.smith@greenlight-npo.org",
        subject="Upgrade Question: Pro-rata billing",
        body="Hi again! We've grown faster than expected and need 5 seats mid-cycle. Do you charge pro-rata?",
        timestamp=datetime.utcnow(),
        category="Billing",
        urgency="Medium",
        requires_human=False,
        confidence=0.88,
        status="Received"
    )
    db.add(db_email)
    db.commit()
    
    res = crm_agent.run_agent(
        email_id=db_email.id,
        message_id="msg_041",
        body=db_email.body,
        sender=db_email.sender,
        thread_id=db_email.thread_id,
        urgency="Medium",
        category="Billing",
        dry_run=True
    )
    
    assert "pro-rata" in res["reply_draft"].lower()
    assert "discount" in res["reply_draft"].lower() or "30%" in res["reply_draft"].lower()
    db.close()

# Cleanup test SQLite file after all tests finish
def test_cleanup_sqlite():
    engine.dispose()
    if os.path.exists("./test_db.db"):
        try:
            os.remove("./test_db.db")
        except PermissionError:
            pass
