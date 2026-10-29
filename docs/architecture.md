# Cynbit Scout: System Architecture Specification

## 1. System Overview & Philosophy
**Cynbit Scout** is an AI Discovery & Lead Intelligence Copilot built for Cynbit Technologies to automate the intake, qualification, commercial scoring, and human-in-the-loop response drafting of inbound client inquiries.

The core engineering philosophy is **Deterministic Resilience with AI Enhancement**:
- The system must function with **100% operational availability**, even when external LLM APIs are offline, rate-limited, or absent.
- Rule-based outputs are **never disguised as LLM output** (`processing_mode` is tracked immutably).
- Client inputs are treated as **untrusted data**, isolated inside strict boundary delimiters to neutralize prompt injection.
- AI drafts **never auto-send**; all communications require human review and approval.

---

## 2. End-to-End Pipeline Architecture

```mermaid
flowchart TD
    subgraph Ingestion["1. Ingestion Layer"]
        A1[Single Inquiry Form Web UI] --> B[Input Validator: Pydantic v2]
        A2[Batch CSV File Upload] --> B
    end

    subgraph Validation["2. Security & Integrity Layer"]
        B -->|Empty / Short <10 chars / Oversized >4000 chars| REJ[Rejection & Error Audit]
        B -->|Duplicate Content Hash SHA-256| DUP[Duplicate Flag & Rejection]
        B -->|Valid Structure| C[Prompt Security Guard]
        C -->|Intercepted Injection Pattern| SEC[Neutralize Delimiters & Tag 'injection_detected']
        C -->|Benign Payload| DELIM[Wrap in XML: untrusted_client_inquiry]
    end

    subgraph Routing["3. Dual-Mode Extraction Engine"]
        SEC --> D{Execution Router}
        DELIM --> D
        D -->|API Key Present & Mode != rules_only| E[LLM Extraction Engine: Gemini / OpenAI]
        D -->|No API Key / Timeout >8s / Mode == rules_only| F[Deterministic Rules-Based Extractor]

        E -->|Strict Schema Check| G{Pydantic Valid?}
        G -->|Valid JSON| EXT[ExtractedLead Schema]
        G -->|Malformed / Invalid| H[Self-Repair Prompt: 1 Retry Attempt]
        H -->|Repair Succeeded| EXT
        H -->|Repair Failed| F
        F --> EXT
    end

    subgraph Scoring["4. Transparent Priority Scoring"]
        EXT --> SC[Priority Scorer: 4-Factor Weighted Model]
        SC -->|Urgency 30% + Budget 25% + Fit 30% + Completeness 15%| SCORE[Priority Score 0-100 & Tier: HIGH / MED / LOW]
    end

    subgraph Intelligence["5. Human-in-the-Loop Intelligence"]
        SCORE --> GEN[Response Generator Engine]
        GEN --> SUM[3-Sentence Executive Summary]
        GEN --> QUES[3-5 Targeted Clarifying Questions]
        GEN --> DRAFT[Watermarked Draft Email: DRAFT - Requires Human Approval]
    end

    subgraph Storage["6. Persistence & Presentation"]
        SUM & QUES & DRAFT --> DB[(SQLite Database: leads, extractions, audit_logs)]
        DB --> UI[Streamlit Interactive Dashboard]
        UI --> AUDIT[Manual Category Correction & Audit Log]
    end
```

---

## 3. Dual-Mode Fallback State Machine

The state machine below details how Cynbit Scout transitions between execution states, ensuring zero runtime crashes:

```mermaid
stateDiagram-v2
    [*] --> InputReceived
    InputReceived --> ValidatingInput: Check length, empty, types
    
    state ValidatingInput {
        [*] --> CheckDuplicates
        CheckDuplicates --> ComputeHash
        ComputeHash --> CheckLength
    }
    
    ValidatingInput --> Rejected: Fails validation
    Rejected --> [*]
    
    ValidatingInput --> SanitizingPayload: Valid
    SanitizingPayload --> CheckingMode: Injection flagged or cleared
    
    state CheckingMode {
        [*] --> InspectEnvironment
        InspectEnvironment --> RulesOnly: DEFAULT_MODE == 'rules_only'
        InspectEnvironment --> CheckAPIKey: DEFAULT_MODE in ['hybrid', 'llm_only']
        CheckAPIKey --> RulesOnly: No GEMINI_API_KEY / OPENAI_API_KEY
        CheckAPIKey --> LLMAttempt: API Key Present
    }
    
    state LLMAttempt {
        [*] --> PrimaryInference: Timeout 8s
        PrimaryInference --> SchemaValidation: Output received
        PrimaryInference --> LLMFailure: Timeout / Network error
        SchemaValidation --> LLMSuccess: Schema matches Pydantic
        SchemaValidation --> RepairAttempt: Schema violation
        RepairAttempt --> LLMSuccess: Repaired successfully
        RepairAttempt --> LLMFailure: Repair failed
    }
    
    LLMFailure --> RulesFallback: Switch to deterministic rules
    RulesOnly --> RulesExecution
    RulesFallback --> RulesExecution: Stamp processing_mode = 'RULES_FALLBACK'
    LLMSuccess --> Scoring: Stamp processing_mode = 'LLM'
    RulesExecution --> Scoring
    
    Scoring --> Generation: Compute weighted priority
    Generation --> SQLitePersist: Assemble LeadRecord
    SQLitePersist --> StreamlitRender: Commit to database
    StreamlitRender --> [*]
```

---

## 4. Database Entity-Relationship Model (SQLite)

Cynbit Scout persists leads with relational integrity, tracking the raw payload, parsed attributes, scoring breakdown, and human audit logs.

```mermaid
erDiagram
    LEADS ||--|| EXTRACTIONS : "has"
    LEADS ||--o{ AUDIT_LOGS : "generates"

    LEADS {
        string id PK "Unique UUID"
        string created_at "ISO 8601 UTC timestamp"
        string content_hash "SHA-256 hash of normalized text"
        string raw_text "Raw unstructured client inquiry"
        string sender_name "Contact name"
        string sender_email "Contact email"
        string company_name "Organization name"
        string source "single_form | csv_upload"
        string status "NEW | QUALIFIED | REVIEWED | DISQUALIFIED | CONTACTED"
        float priority_score "Weighted priority (0-100)"
        string priority_tier "HIGH | MEDIUM | LOW"
        string summary "3-sentence executive summary"
        string follow_up_questions "JSON array of 3-5 questions"
        string draft_reply "Watermarked draft email text"
        string processing_mode "LLM | RULES_FALLBACK"
        int injection_detected "0 or 1 boolean"
        string validation_warnings "JSON array of warnings"
        string manual_category_override "Auditor overridden category"
        string last_audit_timestamp "Timestamp of latest manual edit"
    }

    EXTRACTIONS {
        string lead_id PK, FK "References LEADS.id"
        string business_problem "Extracted core business problem"
        string services "JSON array of CynbitServiceOfferings"
        string budget_tier "BudgetTier enum value"
        string budget_raw "Raw budget text if present"
        string urgency "UrgencyLevel enum value"
        string urgency_raw "Raw timeline text if present"
        string industry "Inferred client industry"
        string missing_information "JSON array of missing attributes"
        float confidence_score "Extraction confidence (0.0 - 1.0)"
        string factor_breakdown "JSON object with 4 factor scores"
        string explanation "Human-readable formula explanation"
    }

    AUDIT_LOGS {
        int id PK "Autoincrement primary key"
        string lead_id FK "References LEADS.id"
        string timestamp "ISO 8601 UTC timestamp"
        string field_name "Modified field (e.g. category)"
        string old_value "Prior value"
        string new_value "Corrected value"
        string auditor "Name or ID of reviewer"
        string reason "Auditor justification note"
    }
```

---

## 5. Security & Isolation Architecture

1. **Untrusted Data Boundary**: User text is treated as an active threat vector. Before entering any LLM prompt, text is sanitized (delimiter sequences stripped) and placed inside `<untrusted_client_inquiry>...</untrusted_client_inquiry>`.
2. **Adversarial Pattern Detector**: Intercepts roleplay jailbreaks (DAN mode), instruction overrides ("ignore previous instructions"), and prompt extraction attempts.
3. **PII Protection**: Regex scrubbers mask email addresses (`u***@domain.com`) and telephone numbers before writing to terminal logs.
4. **Secret Isolation**: Zero API keys are hardcoded in the codebase. Keys are loaded via `.env` and omitted from git tracking.
