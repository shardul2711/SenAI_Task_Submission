import os
import uuid
import asyncio
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.config import settings
from app.database import get_db, SessionLocal, engine
from app.models import Base, Email, Thread, Contact, Action, AuditLog, KnowledgeChunk
from app.schemas import (
    UserLogin, Token, EmailIngestRequest, EmailIngestResponse, EmailSchema,
    ThreadSchema, ContactSchema, ActionSchema, DraftUpdateSchema, ContactStatusUpdateSchema,
    DashboardStats, SentimentPoint, CategoryCount, RAGSearchResponse, AuditLogSchema
)
from app.auth import (
    ADMIN_USERNAME, ADMIN_HASHED_PASSWORD, verify_password, create_access_token, get_current_user
)
from app.services.heuristic import analyze_heuristics
from app.services.llm import analyze_with_llm
from app.services.rag import rag_service
from app.services.scraper import scraper_service
from app.services.agent import crm_agent
from app.ws import manager
import app.crud as crud

# Create database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Agentic CRM Intelligence Platform API",
    description="Backend services for parsing emails, running RAG search, executing LangGraph workflows, and managing live CRM queues.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Job Tracker
jobs = {}

# Custom Exception Handler for Standard Error Envelopes
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": f"ERR_{exc.status_code}",
            "message": exc.detail,
            "details": exc.headers.get("X-Error-Details") if exc.headers else "API Request Error"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "ERR_500",
            "message": "Internal Server Error",
            "details": str(exc)
        }
    )

# --- Background Worker Ingestion Logic ---
async def process_email_worker(job_id: str, payload: Dict[str, Any]):
    """
    Asynchronously executes Layer 2 classification, RAG search,
    sentiment alerts, and the LangGraph Autonomous Agent loop.
    """
    db = SessionLocal()
    try:
        sender = payload["sender"]
        thread_id = payload["thread_id"]
        message_id = payload["message_id"]
        subject = payload.get("subject") or "(No Subject)"
        body = payload.get("body") or ""
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
        except Exception:
            timestamp = datetime.utcnow()

        # Step 1: Run Layer 1 Heuristics Pre-filter
        heuristic_res = analyze_heuristics(sender, subject, body)
        cleaned_body = heuristic_res["cleaned_body"]
        
        # Truncate very long bodies (>10,000 chars) for LLM safety
        if len(cleaned_body) > 10000:
            cleaned_body = cleaned_body[:10000] + "\n... [TRUNCATED DUE TO SIZE]"

        # Step 2: Thread linking (Write to DB immediately)
        db_thread = crud.get_thread_by_id(db, thread_id)
        if not db_thread:
            db_thread = crud.create_thread(db, thread_id, subject, sender)
        
        # Step 3: Check Contact Profile
        db_contact = crud.get_contact_by_email(db, sender)
        if not db_contact:
            db_contact = crud.create_contact(db, sender)

        # Step 4: Run RAG Search to retrieve context
        rag_chunks = rag_service.search(cleaned_body, top_k=3)
        
        # Step 5: Run Layer 2 LLM Classifier
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
            # Non-spam/non-internal: Call LLM
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

        # Update contact last_contact_at
        db_contact.last_contact_at = timestamp
        db.commit()

        # Step 7: Sentiment Deterioration Check (3 consecutive negative emails)
        # Fetch thread emails
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
                agent_reasoning_log="Auto-escalated: Sentiment deterioration (3 consecutive negative emails detected).",
                proposed_content="System notice: Customer sentiment has deteriorated below threshold across multiple emails."
            )
            crud.create_audit_log(
                db=db,
                entity_type="thread",
                entity_id=thread_id,
                action="sentiment_deterioration_escalation",
                performed_by="system",
                diff={"negative_count": negative_count}
            )

        # Step 8: Run LangGraph Agent Node Loops
        if category == "Spam":
            db_email.status = "Ignored"
            db_thread.status = "Ignored"
            db.commit()
            crud.create_action(
                db=db,
                email_id=db_email.id,
                action_type="Ignored",
                agent_reasoning_log="Layer 1: Marked as spam by Heuristics engine. Automatic routing to Ignored.",
                proposed_content=None
            )
        elif category == "Internal":
            pass # Route to internal queue, no auto-reply
        else:
            # Run LangGraph Agent workflow
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
            
        jobs[job_id]["status"] = "completed"
        
        # Broadcast the update event to all connected dashboard WebSockets
        await manager.broadcast({
            "type": "email_ingested",
            "data": {
                "message_id": message_id,
                "thread_id": thread_id,
                "sender": sender,
                "category": category,
                "urgency": urgency
            }
        })
        
    except Exception as e:
        print(f"Error in background ingestion processing: {e}")
        jobs[job_id]["status"] = "failed"
    finally:
        db.close()

# --- Authentication APIs ---
@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, ADMIN_HASHED_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": form_data.username, "role": "admin"})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Ingestion APIs ---
@app.post("/api/ingest", response_model=EmailIngestResponse)
async def ingest_email(request: EmailIngestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Ingest a new email. Validates schema, checks for duplicates,
    performs immediate Layer 1 heuristical routing, and queues Layer 2/Agent pipelines.
    """
    # 1. Deduplication check
    existing = crud.get_email_by_message_id(db, request.message_id)
    if existing:
        return EmailIngestResponse(
            job_id="duplicate",
            status="completed",
            message_id=request.message_id,
            thread_id=request.thread_id
        )

    # 2. Schema / Body Checks
    if not request.body or not request.body.strip():
        # Handle empty/whitespace bodies by substituting placeholder
        request.body = "(Empty email body)"

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing", "message_id": request.message_id, "thread_id": request.thread_id}

    # Queue background task
    background_tasks.add_task(
        process_email_worker,
        job_id,
        request.model_dump()
    )

    return EmailIngestResponse(
        job_id=job_id,
        status="processing",
        message_id=request.message_id,
        thread_id=request.thread_id
    )

@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id == "duplicate":
        return {"job_id": "duplicate", "status": "completed"}
    if job_id not in jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job ID not found")
    return {"job_id": job_id, "status": jobs[job_id]["status"]}

# --- Dashboard & Thread APIs ---
@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return crud.get_dashboard_stats(db)

@app.get("/api/threads/{contact_email}", response_model=List[ThreadSchema])
async def get_threads_by_email(contact_email: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Fetches full thread lists and inner emails/actions for a contact.
    Target speed: <100ms.
    """
    threads = crud.get_threads_by_contact_email(db, contact_email)
    return threads

@app.post("/api/respond/{email_id}")
async def send_manual_response(email_id: int, response_body: DraftUpdateSchema, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_email = db.query(Email).filter(Email.id == email_id).first()
    if not db_email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    db_email.status = "Replied"
    db_email.requires_human = False
    if db_email.thread:
        db_email.thread.status = "Resolved"
        
    crud.create_action(
        db=db,
        email_id=email_id,
        action_type="Auto-Reply",
        agent_reasoning_log="Manual response sent by agent/operator.",
        proposed_content=response_body.proposed_content
    )
    db.commit()
    return {"status": "success", "message": "Manual response sent"}

@app.patch("/api/drafts/{id}", response_model=ActionSchema)
async def edit_proposed_draft(id: int, draft: DraftUpdateSchema, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    action = crud.update_draft_content(db, id, draft.proposed_content)
    if not action:
        raise HTTPException(status_code=404, detail="Draft not found")
    return action

@app.post("/api/drafts/{id}/approve", response_model=ActionSchema)
async def approve_draft(id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    action = crud.approve_action(db, id, approved_by=current_user["username"])
    if not action:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Broadcast updates to WebSockets
    await manager.broadcast({
        "type": "draft_approved",
        "data": {
            "action_id": id,
            "email_id": action.email_id
        }
    })
    return action

# --- Analytics APIs ---
@app.get("/api/analytics/sentiment-trend", response_model=List[SentimentPoint])
async def get_sentiment_trend(sender: Optional[str] = None, days: int = 30, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return crud.get_sentiment_trend(db, sender, days)

@app.get("/api/analytics/category-breakdown", response_model=List[CategoryCount])
async def get_category_breakdown(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return crud.get_category_breakdown(db)

# --- Core Modules APIs ---
@app.get("/api/rag/search", response_model=List[RAGSearchResponse])
async def get_rag_search(q: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return rag_service.search(q)

@app.get("/api/intelligence/reputation")
async def get_web_intelligence(company: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return await scraper_service.get_intelligence(db, company)

@app.post("/api/agent/dry-run/{email_id}")
async def dry_run_agent(email_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Runs the LangGraph agent in planning mode without committing actions.
    """
    db_email = db.query(Email).filter(Email.id == email_id).first()
    if not db_email:
        raise HTTPException(status_code=404, detail="Email record not found")
        
    final_state = crm_agent.run_agent(
        email_id=db_email.id,
        message_id=db_email.message_id,
        body=db_email.body,
        sender=db_email.sender,
        thread_id=db_email.thread_id,
        urgency=db_email.urgency,
        category=db_email.category,
        dry_run=True
    )
    
    return {
        "email_id": email_id,
        "action_type": final_state["action_type"],
        "proposed_reply": final_state["reply_draft"],
        "reasoning_logs": final_state["reasoning_logs"]
    }

@app.get("/api/audit/{entity_type}/{entity_id}", response_model=List[AuditLogSchema])
async def get_audit_history(entity_type: str, entity_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return crud.get_audit_logs_for_entity(db, entity_type, entity_id)

@app.get("/api/contacts/{email}", response_model=ContactSchema)
async def get_contact_profile(email: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    contact = crud.get_contact_by_email(db, email)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@app.patch("/api/contacts/{email}/status", response_model=ContactSchema)
async def update_contact_status(email: str, schema: ContactStatusUpdateSchema, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    contact = crud.update_contact_status(db, email, schema.status)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

# --- WebSockets Endpoint ---
@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We just keep the connection open and receive heartbeats
            data = await websocket.receive_text()
            # Send simple pong response
            await websocket.send_json({"type": "pong", "payload": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket connection error: {e}")
        manager.disconnect(websocket)
