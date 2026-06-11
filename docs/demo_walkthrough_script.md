# Demo Walkthrough Script

This script provides a structured guide to demonstrate the key features of the **Agentic CRM Intelligence Platform** for recordings, code reviews, or presentations.

---

## Preparation
1. Ensure the backend FastAPI server is running (`localhost:8000`).
2. Ensure the frontend Next.js server is running (`localhost:3000`).
3. Open `http://localhost:3000` in your browser.
4. Log in using:
   - **Username**: `admin`
   - **Password**: `admin123`
5. Verify that the WebSocket indicator in the top header says **Socket Connected** (green dot).

---

## Scene 1: Real-Time Email Stream Ingestion

### Objective
Demonstrate the platform's ability to ingest emails in real time, thread them automatically, and update the operator's inbox dynamically using WebSockets.

### Steps
1. On the left sidebar of the frontend dashboard, look at the **Demo Ingestion Replay** panel.
2. Click **Alice Pricing Thread** to trigger a quick ingestion.
3. Observe the bottom of the sidebar: a toast notification appears immediately saying: *New email ingested from alice.smith@greenlight-npo.org*.
4. Look at the inbox list pane. Notice the thread `thread_alice_pricing` appears at the top.
5. In your backend terminal, open the email replay simulator:
   ```bash
   .venv\Scripts\python scripts/replay_emails.py --speed 1.0
   ```
6. Watch the frontend inbox. Notice new emails pop in and the counters on the **Realtime Analytics** tab update dynamically.

---

## Scene 2: Bob Jones SLA Outage & Legal Escalation

### Objective
Demonstrate how the LangGraph agent handles a high-stakes, Critical urgency P0 outage threat.

### Steps
1. In the **Demo Ingestion Replay** sidebar, click **Bob Outage Escalate**.
2. Select the thread **bob.jones@enterprise.net** in the inbox queue.
3. Look at the badge list: it is flagged as **Critical** urgency, **Legal** category, and sentiment **Negative**.
4. Read Bob's email body in the main message stream: *We have reviewed the incident report. The RCA is inadequate... legal team is involved... renewal on hold.*
5. Expand the **Agent Reasoning Logs** panel on the right sidebar. Show the Thought-Action-Observation trace:
   - *Thought*: Identifies legal threat and SLA credit request.
   - *Action*: Calls `get_contact_profile`, `check_account_status` (verifies Bob is an Enterprise customer, billing status is "Renewal On Hold").
   - *Action*: Calls `search_knowledge_base` for `sla_policy.md` (retrieves the 24h RCA delivery commitment).
   - *Action*: Calls `draft_reply` (drafts an empathetic holding reply referencing the credit policies).
   - *Action*: Escalates to legal queue (`Legal-Flag`).
6. Point to the **Proposed Agent Action** card: show the proposed draft reply. Note that because it is a Critical legal threat, it is marked as **Human Operations Required** rather than auto-sending.
7. Click **Approve & Execute** to authorize the draft response.

---

## Scene 3: RAG Retrieval & Policy Citations

### Objective
Show how the agent grounds its responses in the company's internal knowledge base policies instead of hallucinating.

### Steps
1. Select the thread **alice.smith@greenlight-npo.org** in the inbox.
2. Click the email asking about *mid-cycle seat upgrades and nonprofit discounts*.
3. Expand the **Policy Search (RAG)** panel on the right side-panel.
4. Show the retrieved source documents: `pricing_policy.md` and `escalation_matrix.md`.
5. Point to the exact matching chunk snippet shown in the debug pane: *Non-Profit Discount: 30% discount on Standard Plan. Pro-Rata Upgrades: Mid-cycle upgrades charged only for remaining days.*
6. Point out that the drafted response cites these rules exactly, calculating the 30% discount for Alice's Standard Plan seat upgrade.

---

## Scene 4: Karen Churn Threat & Web Intelligence

### Objective
Demonstrate reputation crisis detection, automatic scraping of Trustpilot/G2 scores, and generating refund retention offers.

### Steps
1. In the **Demo Ingestion Replay** sidebar, click **Karen Churn Threat**.
2. Select the thread **karen.w@retail-co.com** in the inbox queue.
3. Note that the category is **Complaint**, urgency is **Critical** (due to churn threat), and sentiment is **Negative**.
4. Point to the right sidebar: notice the **Market Intelligence** card.
5. Highlight the crawled Trustpilot star rating (`4.1 / 5`) and top complaint themes (e.g. *Latency in European region*) that were fetched asynchronously.
6. Look at the proposed response draft: the agent retrieves the refund policy retention guidelines and drafts a customized offer for a 30% service credit discount to prevent churn.

---

## Scene 5: Realtime Operations Analytics Dashboard

### Objective
Show the executive overview of system performance, sentiment tracking, and at-risk CRM accounts.

### Steps
1. Click the **Realtime Analytics** tab on the left navigation sidebar.
2. Walk through the dashboard:
   - **Core Metrics**: View counts for Pending, Replied, Escalated, Critical, and Spam.
   - **Customer Sentiment Trend**: Review the 30-day sentiment moving average chart (Recharts).
   - **Category Distribution**: Highlight the bar chart showing volume breakdown by classification.
   - **At-Risk CRM Accounts**: Show the live list of accounts flagged for high churn risk (e.g., Karen W. with 95% churn score and Bob Jones with 45% churn score).
