-- =========================================================================
-- SenAI CRM Intelligence Platform MySQL DDL Schema
-- Compatible with MySQL 8.0 and MySQL Workbench
-- =========================================================================

CREATE DATABASE IF NOT EXISTS crm_intelligence;
USE crm_intelligence;

-- 1. Contacts Table
CREATE TABLE IF NOT EXISTS contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NULL,
    company VARCHAR(255) NULL,
    status ENUM('VIP', 'Blocked', 'Active', 'Churned') DEFAULT 'Active' NOT NULL,
    account_value DECIMAL(12, 2) DEFAULT 0.00 NOT NULL,
    churn_risk_score FLOAT DEFAULT 0.0 NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_contact_at DATETIME NULL,
    INDEX idx_contacts_email (email),
    INDEX idx_contacts_company (company),
    INDEX idx_contacts_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. Threads Table
CREATE TABLE IF NOT EXISTS threads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL UNIQUE,
    subject VARCHAR(255) NOT NULL,
    sender_email VARCHAR(255) NOT NULL,
    first_seen_at DATETIME NOT NULL,
    last_updated_at DATETIME NOT NULL,
    status ENUM('Open', 'Resolved', 'Escalated', 'Ignored') DEFAULT 'Open' NOT NULL,
    assigned_to VARCHAR(255) NULL,
    INDEX idx_threads_thread_id (thread_id),
    INDEX idx_threads_sender_email (sender_email),
    INDEX idx_threads_last_updated_at (last_updated_at),
    INDEX idx_threads_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 3. Emails Table
CREATE TABLE IF NOT EXISTS emails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    sender VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    sentiment_score FLOAT DEFAULT 0.0 NOT NULL,
    category VARCHAR(50) NULL,
    urgency ENUM('Critical', 'High', 'Medium', 'Low') DEFAULT 'Low' NOT NULL,
    requires_human BOOLEAN DEFAULT FALSE NOT NULL,
    confidence FLOAT DEFAULT 1.0 NOT NULL,
    raw_entities JSON NULL,
    status ENUM('Received', 'Processing', 'Replied', 'Escalated', 'Ignored') DEFAULT 'Received' NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,
    INDEX idx_emails_thread_id (thread_id),
    INDEX idx_emails_message_id (message_id),
    INDEX idx_emails_sender (sender),
    INDEX idx_emails_timestamp (timestamp),
    INDEX idx_emails_sentiment_score (sentiment_score),
    INDEX idx_emails_category (category),
    INDEX idx_emails_urgency (urgency),
    INDEX idx_emails_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 4. Actions Table
CREATE TABLE IF NOT EXISTS actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email_id INT NOT NULL,
    action_type ENUM('Auto-Reply', 'Escalate', 'Legal-Flag', 'Ticket-Created', 'Ignored') NOT NULL,
    agent_reasoning_log TEXT NULL,
    proposed_content TEXT NULL,
    is_approved BOOLEAN DEFAULT FALSE NOT NULL,
    approved_by VARCHAR(255) NULL,
    executed_at DATETIME NULL,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE,
    INDEX idx_actions_email_id (email_id),
    INDEX idx_actions_action_type (action_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 5. Knowledge Chunks Table
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_doc VARCHAR(255) NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    INDEX idx_knowledge_chunks_source_doc (source_doc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 6. Web Intelligence Cache Table
CREATE TABLE IF NOT EXISTS web_intelligence_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_url VARCHAR(500) NOT NULL,
    target_entity VARCHAR(255) NOT NULL,
    scraped_data JSON NOT NULL,
    scraped_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    INDEX idx_web_intel_target_entity (target_entity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 7. Audit Log Table
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    performed_by VARCHAR(255) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    diff JSON NULL,
    INDEX idx_audit_log_entity (entity_type, entity_id),
    INDEX idx_audit_log_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
