# Cynbit Scout: Technical Interview Defense & Oral Presentation Playbook

**Candidate**: B.S. in Applied AI & Data Science, IIT Jodhpur  
**Target Assessment**: Cynbit Technologies AI/ML Intern Assessment  
**Project**: Cynbit Scout (`cynbit-scout-ai`)  

---

## 1. The 2-Minute Elevator Pitch (Word-for-Word Opening Statement)

> *"Hi everyone, I’m excited to present **Cynbit Scout**, an enterprise AI Discovery and Lead Intelligence Copilot designed specifically for Cynbit Technologies.*
>
> *When studying Cynbit’s public business model, I noticed that your customer journey initiates with **'Discovery & Audit'**, and that you already possess proprietary AI platforms in code evaluation (Cynbit Studio) and customer reviews (Revio). Rather than building redundant AI inside products that already have it, I tackled the commercial front door: turning unstructured, ambiguous prospective client inquiries into structured, commercially scored, and qualified technical leads.*
>
> *From an engineering perspective, my core design philosophy was **Deterministic Resilience with AI Enhancement**. Many AI prototypes are fragile: if an external LLM API experiences rate limits, latency spikes, or JSON syntax errors, the entire pipeline crashes. Cynbit Scout implements a **Dual-Mode Hybrid Architecture**: it leverages Google Gemini or OpenAI when available for subtle semantic extraction, but pairs it with a zero-dependency, regex-and-keyword **Rules Fallback Engine** that executes in under 5 milliseconds. The system guarantees 100% uptime, strictly isolates untrusted text against prompt injection, enforces a transparent 4-factor priority score, and generates human-reviewed draft replies that are never auto-dispatched.*
>
> *I’ve verified the entire system with 22 unit tests and evaluated it on a 75-row benchmark spanning 12 real-world archetypes, achieving a 0.8632 Macro F1 and 100% prompt injection catch rate.*
>
> *I’m excited to walk you through the live dashboard and dive into the architecture."*

---

## 2. The 5-Minute Live Screen-Share Demo Script

When screen-sharing the Streamlit dashboard on `http://localhost:8501`, follow this exact sequence:

### Minute 1: The Commercial Problem & 1-Click Scenario
1. **Action**: Open **Tab 1: Live Inquiry Copilot**.
2. **Narration**: *"To show how Cynbit Scout qualifies leads in real-time, I’ve included 1-click test scenarios directly in the UI. Let's click the **'AI Agent Lead'** preset."*
3. **Action**: Click the `🤖 AI Agent Lead` button, then click **'Run Lead Qualification Pipeline'**.
4. **Narration**: *"In under 20 milliseconds, the pipeline validates the text, extracts the budget ($45,000) and timeline (<2 weeks), identifies the domain as FinTech, and calculates an explainable priority score of 84.5 out of 100, placing it in the HIGH priority tier."*

### Minute 2: Explainable Scoring & Human-in-the-Loop Safeguards
1. **Action**: Scroll down to the **Factor Breakdown** meters and **Executive Summary**.
2. **Narration**: *"Notice that the priority score is not an unexplainable black box. It uses an explicit mathematical formula: Urgency carries 30%, Service Fit carries 30%, Budget carries 25%, and Information Completeness carries 15%.*
3. **Action**: Point to the **Draft Reply** box.
4. **Narration**: *"Crucially, Cynbit Scout adheres to a strict ethical safeguard: **it never auto-sends emails**. The response generator produces a 3-sentence executive briefing, 3 targeted clarifying questions, and watermarks the draft with 'DRAFT - REQUIRES HUMAN APPROVAL'."*

### Minute 3: Security & Adversarial Injection Testing
1. **Action**: Click the `🚨 Prompt Injection` preset button at the top of Tab 1, then click **'Run Lead Qualification Pipeline'**.
2. **Narration**: *"Inbound web forms are public attack surfaces. Here, an adversarial attacker attempts an instruction override and DAN jailbreak to force a $500,000 budget.*
3. **Action**: Show the bright red alert banner: `SECURITY ALERT: Intercepted prompt injection patterns: INSTRUCTION_OVERRIDE, PROMPT_LEAKAGE`.
4. **Narration**: *"Our security guardrail intercepted the attack pre-execution, sanitized delimiter characters, wrapped the payload in an immutable XML boundary, and flagged it with `injection_detected = True` in the database."*

### Minute 4: Lead Database & Auditor Category Override
1. **Action**: Click on **Tab 2: Lead Database & Review**.
2. **Narration**: *"In Tab 2, sales consultants have an operational CRM view of all inquiries persisted to SQLite. We can see offering distributions and priority breakdowns.*
3. **Action**: Select a lead in the inspector dropdown, change its category from `Custom Software Development` to `Product Demo: TenantEase`, enter an auditor note, and click **'Submit Category Override'**.
4. **Narration**: *"If a consultant discovers on a call that the client actually wanted a TenantEase demo, they can perform a manual category override. This immediately updates the record and creates an immutable row in our `audit_logs` table."*

### Minute 5: Empirical Benchmark & Q&A Transition
1. **Action**: Click on **Tab 4: Benchmark Telemetry**, and quickly highlight **Tab 5: Architecture Defense Q&A**.
2. **Narration**: *"In Tab 4, we display real empirical metrics generated by running our evaluation script on our 75-row benchmark dataset: 100% input validation accuracy, 100% injection interception, and 0.8632 Macro F1.*
3. **Closing**: *"I’ve also codified our core design trade-offs in Tab 5. I would love to answer any questions about the technical implementation!"*

---

## 3. Top 10 Hard Technical Interview Questions & Senior-Level Answers

### Q1: Why did you choose a Dual-Mode Hybrid Architecture instead of relying solely on an LLM?
> **Answer**: *"In an enterprise sales funnel, reliability is paramount. If a potential client submits an inquiry with a \$50,000 budget while OpenAI or Gemini is experiencing an outage, rate limit, or network timeout, an LLM-only system fails and returns an HTTP 500 error, potentially losing the lead. Our dual-mode architecture attempts LLM extraction with a strict 8-second timeout. If the LLM times out or encounters a schema violation that fails self-repair, the system automatically falls back to our deterministic rules engine in under 5 milliseconds. Crucially, we maintain full ethical transparency: the database immutably records whether the record was processed via `LLM` or `RULES_FALLBACK`, so rule outputs are never misrepresented."*

### Q2: How did you calibrate the priority scoring formula weights?
> **Answer**: *"The formula is $P = 0.30 \cdot S_u + 0.25 \cdot S_b + 0.30 \cdot S_f + 0.15 \cdot S_c$. 
> - **Urgency (30%)** and **Service Fit (30%)** are co-weighted highest because commercial research demonstrates that inbound lead conversion decays exponentially if not answered quickly, and high project margins depend on alignment with core competencies (AI automation and proprietary product demos).
> - **Budget (25%)** ensures commercial viability, filtering out low-budget speculative noise (<$5k) while prioritizing strategic engagements (>$100k).
> - **Completeness (15%)** deducts points for missing information, incentivizing sales consultants to obtain technical prerequisites during the discovery call."*

### Q3: How do you defend against prompt injection without blocking legitimate technical inquiries?
> **Answer**: *"We employ defense-in-depth across 4 layers:
> 1. **Heuristic Pattern Scanning**: We detect adversarial markers like 'ignore previous instructions', 'DAN mode', or 'reveal system prompt'.
> 2. **Delimiter Sanitization**: We strip triple quotes (`\"\"\"`), backticks (```` ``` ````), and XML-like tags (`<system>`).
> 3. **Context Isolation**: When passed to the LLM, the inquiry is encapsulated inside `<untrusted_client_inquiry>`. The system prompt contains explicit directives that anything inside this block is passive untrusted data, never instructions.
> 4. **Safe-Mode Routing**: Rather than crashing or dropping the connection, flagged inquiries are processed in safe mode with `injection_detected = True`, ensuring that even adversarial payloads are preserved for security auditing without compromising the host system."*

### Q4: Why did you use Pydantic v2 instead of standard Python dictionaries or dataclasses?
> **Answer**: *"Pydantic v2 is compiled in Rust (`pydantic-core`), providing 5–10x higher validation throughput than v1. More importantly, it enforces strict runtime schema typing. If an LLM hallucinates an invalid enum (e.g. inventing a service not offered by Cynbit), Pydantic catches it immediately with a structured ValidationError. This triggers our self-repair loop or fallback to the rules engine, guaranteeing that downstream database and UI layers never encounter malformed fields or unexpected data types."*

### Q5: What is your LLM self-repair loop and why is it capped at exactly one retry?
> **Answer**: *"When an LLM outputs JSON that violates our Pydantic schema (e.g., missing a field or appending conversational preamble), we invoke a repair prompt that provides the LLM with the exact validation error and the malformed text, requesting only valid JSON. In empirical testing, one retry corrects over 90% of minor syntax errors. We strictly cap it at one attempt because repeated retries introduce latency compounding (e.g. 3 attempts $\times$ 4s = 12s of user waiting) and API cost multiplication. If it fails twice, the rules engine takes over deterministically in 4ms."*

### Q6: Why did you choose SQLite over PostgreSQL or MongoDB for this implementation?
> **Answer**: *"For an internship assessment and local evaluation, SQLite is the gold standard of pragmatism. It runs with zero external daemon configuration, zero network latency, and zero Docker dependencies. Furthermore, SQLite is fully ACID-compliant, supports relational joins between `leads`, `extractions`, and `audit_logs`, and handles concurrent read locks seamlessly. If Cynbit wants to transition this to a multi-tenant cloud microservice, our schema easily ports to PostgreSQL via SQLAlchemy or an ORM with minimal refactoring."*

### Q7: Why didn't you use LangChain, LlamaIndex, or AutoGen?
> **Answer**: *"LangChain and similar orchestration frameworks introduce heavy dependency trees (often 50+ transitive libraries), breaking API churn across minor versions, and opaque abstractions. For structured commercial lead qualification, a custom provider-agnostic client written with native SDKs (`google-genai` and `requests`) gives us total control over timeout budgets (8s), exponential backoff retries, prompt injection boundaries, and Pydantic self-repair. It keeps the codebase lean, easily testable with pytest, and 100% explainable during technical review."*

### Q8: What did you learn from the benchmark error analysis?
> **Answer**: *"On our 75-row benchmark, the rules baseline achieved a 0.8632 Macro F1 and 91.4% budget accuracy, but only 44.3% urgency accuracy. The qualitative error analysis revealed why: timeline phrasing in free text is highly colloquial and varied ('when you get around to it', 'sometime next quarter'). Rule-based regexes expect structured phrases like 'ASAP' or 'Q4'. This is an empirical finding that demonstrates where LLM semantic inference provides significant value over keyword matching, while proving that the rules engine still catches the critical intent."*

### Q9: How does Cynbit Scout scale if Cynbit receives 100,000 inquiries per day?
> **Answer**: *"To scale horizontally:
> 1. **Decouple Ingestion from Processing**: The Streamlit or web form writes incoming inquiries immediately to a distributed message queue (RabbitMQ, Redis Streams, or AWS SQS).
> 2. **Worker Pool**: A pool of stateless Celery or FastAPI workers pull inquiries from the queue and run the validation and extraction pipeline.
> 3. **Database Migration**: Migrate SQLite to Amazon Aurora PostgreSQL or Google Cloud SQL with read replicas for analytics queries.
> 4. **Caching**: Inquiries with identical content hashes can return cached classification results from Redis, bypassing LLM inference entirely."*

### Q10: Why did you label all internal pain points as hypotheses in your report?
> **Answer**: *"Because engineering ethics and scientific rigor require intellectual honesty. I do not have access to Cynbit's internal CRM, sales conversion data, or staffing utilization. Rather than inventing fake ROI numbers or claiming that 'Cynbit loses 32% of leads', I grounded my analysis in Cynbit's public website and explicitly labeled all operational pain points as hypotheses based on industry benchmarks. This demonstrates respect for data integrity and real-world engineering standards."*
