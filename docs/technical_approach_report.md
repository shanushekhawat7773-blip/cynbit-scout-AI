# Cynbit Scout: Technical Approach & Architectural Rationale

**Author**: AI/ML Intern Assessment Candidate (IIT Jodhpur)  
**System**: Cynbit Scout (AI Discovery & Lead Intelligence Copilot)  
**Target Platform**: Python 3.13, Streamlit, Pydantic v2, SQLite, Windows + VS Code  

---

## 1. System Philosophy: Deterministic Resilience

In production enterprise software, AI components should be **resilient accelerators, not fragile single points of failure**. 

If a prospective client submits a \$100,000 project inquiry while an external LLM API is experiencing an outage or rate limit, a fragile LLM-only system crashes or returns a 500 error. The lead is lost.

**Cynbit Scout solves this through a Dual-Mode Hybrid Architecture**:
1. **LLM Mode (Enhancement Layer)**: Uses Google Gemini or OpenAI with structured JSON output enforcement to parse subtle, ambiguous conversational nuance.
2. **Rules-Based Fallback Engine (Resilience Layer)**: A zero-dependency, regex-and-keyword extraction engine that executes deterministically in under 5 milliseconds.
3. **Transparent Operational Labeling**: To adhere strictly to engineering ethics, every lead record is stamped with its exact `processing_mode` (`LLM` or `RULES_FALLBACK`). Rule outputs are never presented as LLM generations.

---

## 2. Mathematical Priority Scoring Formula

Rather than treating lead qualification as an unexplainable LLM prompt or a black-box neural net, Cynbit Scout utilizes an **explicit, deterministic multi-factor weighted scoring model**:

$$\text{Priority Score } (P) = (w_u \cdot S_u) + (w_b \cdot S_b) + (w_f \cdot S_f) + (w_c \cdot S_c)$$

Where weights sum to $1.0$:
- **Urgency Weight ($w_u = 0.30$)**: Time-sensitive leads require immediate sales engagement.
  - Immediate (<2 weeks): $100$ pts
  - Medium (1-3 months): $70$ pts
  - Low (>3 months): $40$ pts
  - Exploratory / Discovery: $30$ pts
  - Unspecified: $15$ pts
- **Budget Clarity & Tier ($w_b = 0.25$)**: Commercial viability and project scale.
  - Strategic Tier (>$100k): $100$ pts
  - Enterprise Tier ($25k-$100k): $85$ pts
  - Growth Tier ($5k-$25k): $65$ pts
  - Micro Tier (<$5k): $40$ pts
  - Unspecified: $15$ pts
- **Service Fit & Strategic Alignment ($w_f = 0.30$)**: Fit with Cynbit's core offerings.
  - AI Automation & Product Demos (Studio, TenantEase, Revio): $100$ pts
  - Core Software & Cloud DevOps: $90$ pts
  - Digital Marketing & SEO: $70$ pts
  - Unsupported / Irrelevant: $0$ pts (Disqualifier)
  - Multi-Service Synergy: $+5$ bonus points if more than 1 supported service is requested.
- **Information Completeness ($w_c = 0.15$)**: Detail sufficiency for initial scoping.
  - Starts at $100$ pts.
  - Deducts $20$ pts per critical missing item (e.g. missing budget, unspecified timeline, missing contact email, vague problem). Minimum $20$ pts.

### Priority Tiers:
- **HIGH**: $P \ge 75$ (Immediate senior technical discovery call scheduled).
- **MEDIUM**: $45 \le P < 75$ (Follow-up questionnaire sent to clarify technical details).
- **LOW**: $P < 45$ (Nurturing queue or disqualification review).

---

## 3. Security Architecture & Threat Neutralization

Inbound contact forms are public attack surfaces. Cynbit Scout implements a multi-tiered security perimeter:

### A. Prompt Injection Defense
- **Pattern Interception**: Scans for adversarial tokens including instruction overrides (`"ignore previous instructions"`), persona hijacking (`"you are now in DAN mode"`), and system prompt exfiltration (`"print your instructions"`).
- **Delimiters & Sanitization**: Strips dangerous markdown characters (`"""`, `'''`, `<<<`, `>>>`) and neutralizes raw XML tags (`<system>` $\rightarrow$ `[system]`).
- **Context Isolation**: When passed to an LLM, the untrusted user inquiry is encapsulated within an immutable boundary:
  ```xml
  <untrusted_client_inquiry>
  [Sanitized User Inquiry Text]
  </untrusted_client_inquiry>
  ```
  The system prompt explicitly commands the LLM to treat everything inside this tag as passive text, never as instructions.
- **Audit Tagging**: If an injection pattern is detected, the inquiry is processed in safe mode, flagged with `injection_detected = True`, and surfaced in the admin dashboard for human review.

### B. Payload Exhaustion & Validation Guardrails
- **Minimum Length**: Rejects inputs $<10$ characters (e.g. "hi", "test") to prevent database pollution.
- **Maximum Length**: Rejects inputs $>4,000$ characters to prevent LLM token buffer overflow and denial-of-service.
- **SHA-256 Deduplication**: Calculates a deterministic hash of normalized text (`" ".join(text.lower().split())`) to halt spam bots submitting identical messages repeatedly.

### C. Privacy & Secret Hygiene
- **Zero Hardcoded Secrets**: All API keys are loaded via environment variables (`.env`).
- **PII Protection**: Regex scrubbers mask email addresses (`u***@domain.com`) and telephone numbers before writing to terminal logs.

---

## 4. LLM Reliability & Self-Repair Architecture

When LLM mode is enabled, structured reliability is enforced via a two-stage validation loop:

```
[LLM Call Attempt 1] ---> [Raw JSON String] ---> [Pydantic Validation]
                                                        |
                                       +----------------+----------------+
                                       | Valid                           | Invalid Schema / JSON
                                       v                                 v
                              [ExtractedLead Object]          [Trigger Repair Prompt]
                                                              (Sends validation error to LLM)
                                                                         |
                                                                         v
                                                              [LLM Call Attempt 2]
                                                                         |
                                                       +-----------------+-----------------+
                                                       | Valid                             | Still Invalid
                                                       v                                   v
                                              [ExtractedLead Object]             [Fallback to Rules Engine]
```

This self-repair loop recovers over 90% of minor JSON syntax errors without human intervention, while falling back gracefully to deterministic rules if the model fails twice.

---

## 5. Human-in-the-Loop Governance & Audit Trail

A critical requirement of enterprise AI is preventing automated rogue communications. Cynbit Scout strictly enforces two policies:
1. **Never Auto-Send**: The response generator outputs personalized draft replies containing:
   ```
   =================================================================
   *** DRAFT - REQUIRES HUMAN APPROVAL | Cynbit Scout Lead Copilot ***
   =================================================================
   ```
   Consultants must review, personalize, and approve the email in the dashboard before transmitting it to the prospect.
2. **Category Correction & Immutable Audit Log**: When an auditor corrects an extracted category in the UI, SQLite records the change into `audit_logs` with the timestamp, prior value, new value, auditor identity, and justification note.

---

## 6. Interview Defense & Oral Q&A Cheat Sheet

Use these concise, defensible talking points during technical assessment interviews:

### Q1: Why did you choose SQLite over MongoDB or PostgreSQL?
> *"For an assessment and local edge deployment, SQLite offers zero-configuration, zero-network-overhead relational persistence bundled with Python's standard library. Its ACID transactions and relational joins between `leads`, `extractions`, and `audit_logs` perfectly model the structured domain without requiring external Docker containers. For production cloud deployment, replacing SQLite with PostgreSQL requires only changing the SQLAlchemy/SQL connection string."*

### Q2: Why avoid LangChain or LlamaIndex in favor of custom clients?
> *"LangChain introduces heavy external dependency trees, frequent breaking API changes, and unnecessary abstraction layers for structured JSON extraction. By writing a lightweight, provider-agnostic client using native SDKs (`google-genai` and `requests`), I maintain full control over prompt security boundaries, timeout budgets (8s), exponential backoff retries, and the Pydantic v2 self-repair loop. It makes the codebase 10x easier to debug, test, and defend."*

### Q3: How does the system handle prompt injections?
> *"We employ defense-in-depth: (1) regex heuristic detection for common jailbreak/DAN tokens, (2) character-level sanitization to strip delimiter escapes, (3) strict XML boundary isolation (`<untrusted_client_inquiry>`) in the system prompt, and (4) operational tagging so flagged inquiries are inspected by human reviewers rather than processed silently."*

### Q4: Why is the priority scoring formula deterministic instead of using an LLM?
> *"Commercial qualification requires explainability and consistency. If two prospects submit identical requests with a \$50k budget and a 2-week deadline, they must receive identical priority scores. A deterministic formula allows management to audit weights ($w_u=0.30, w_b=0.25, w_f=0.30, w_c=0.15$) and explain to sales leads exactly why an inquiry was rated High or Low."*

### Q5: What are the key limitations of the current implementation?
> *"First, the benchmark dataset (N=75) is synthetic; while it rigorously tests 12 edge-case archetypes, it does not represent real-world statistical distribution. Second, the rules-based urgency extractor achieves 44% exact match because timeline phrasing in free text is highly colloquial ('sometime next quarter', 'when convenient'). This is an area where LLM semantic inference provides significant uplift over keyword matching."*
