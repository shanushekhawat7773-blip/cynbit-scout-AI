"""
SQLite persistence and audit logging layer for Cynbit Scout.
Stores incoming leads, extracted attributes, priority metrics, and human-in-the-loop manual corrections.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from cynbit_scout.models.schemas import (
    BudgetTier,
    CynbitServiceOffering,
    ExtractedLead,
    FactorBreakdown,
    LeadRecord,
    LeadStatus,
    PriorityTier,
    ProcessingMode,
    UrgencyLevel,
)


class DatabaseManager:
    """
    Manages SQLite database operations, schema creation, lead persistence, and audit logs.
    """

    def __init__(self, db_path: str = "data/cynbit_scout.db"):
        self.db_path = db_path
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Establish connection with row factory enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Create database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main Leads Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    sender_name TEXT,
                    sender_email TEXT,
                    company_name TEXT,
                    source TEXT DEFAULT 'single_form',
                    status TEXT DEFAULT 'NEW',
                    priority_score REAL NOT NULL,
                    priority_tier TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    follow_up_questions TEXT NOT NULL,
                    draft_reply TEXT NOT NULL,
                    processing_mode TEXT NOT NULL,
                    injection_detected INTEGER DEFAULT 0,
                    validation_warnings TEXT DEFAULT '[]',
                    manual_category_override TEXT,
                    last_audit_timestamp TEXT
                )
            """)

            # Extracted Lead Attributes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS extractions (
                    lead_id TEXT PRIMARY KEY,
                    business_problem TEXT NOT NULL,
                    services TEXT NOT NULL,
                    budget_tier TEXT NOT NULL,
                    budget_raw TEXT,
                    urgency TEXT NOT NULL,
                    urgency_raw TEXT,
                    industry TEXT NOT NULL,
                    missing_information TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    factor_breakdown TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
                )
            """)

            # Audit Trail for Human Corrections
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    auditor TEXT DEFAULT 'human_reviewer',
                    reason TEXT,
                    FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
                )
            """)

            conn.commit()

    def save_lead(self, record: LeadRecord) -> None:
        """Insert or replace a lead record and its extractions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert lead
            cursor.execute("""
                INSERT OR REPLACE INTO leads (
                    id, created_at, content_hash, raw_text, sender_name, sender_email,
                    company_name, source, status, priority_score, priority_tier,
                    summary, follow_up_questions, draft_reply, processing_mode,
                    injection_detected, validation_warnings, manual_category_override,
                    last_audit_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                record.created_at,
                record.content_hash,
                record.raw_text,
                record.sender_name,
                record.sender_email,
                record.company_name,
                record.source,
                record.status.value,
                record.priority_score,
                record.priority_tier.value,
                record.summary,
                json.dumps(record.follow_up_questions),
                record.draft_reply,
                record.processing_mode.value,
                1 if record.injection_detected else 0,
                json.dumps(record.validation_warnings),
                record.manual_category_override,
                record.last_audit_timestamp,
            ))

            # Insert extractions
            ext = record.extracted
            cursor.execute("""
                INSERT OR REPLACE INTO extractions (
                    lead_id, business_problem, services, budget_tier, budget_raw,
                    urgency, urgency_raw, industry, missing_information,
                    confidence_score, factor_breakdown, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                ext.business_problem,
                json.dumps([s.value for s in ext.services]),
                ext.budget_tier.value,
                ext.budget_raw,
                ext.urgency.value,
                ext.urgency_raw,
                ext.industry,
                json.dumps(ext.missing_information),
                ext.confidence_score,
                json.dumps(record.factor_breakdown.model_dump()),
                record.explanation,
            ))

            conn.commit()

    def get_all_leads(self) -> List[LeadRecord]:
        """Fetch all leads joined with extractions ordered by created_at desc."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    l.*,
                    e.business_problem, e.services, e.budget_tier, e.budget_raw,
                    e.urgency, e.urgency_raw, e.industry, e.missing_information,
                    e.confidence_score, e.factor_breakdown, e.explanation
                FROM leads l
                LEFT JOIN extractions e ON l.id = e.lead_id
                ORDER BY l.created_at DESC
            """)
            rows = cursor.fetchall()

            records: List[LeadRecord] = []
            for row in rows:
                record = self._row_to_lead_record(row)
                if record:
                    records.append(record)
            return records

    def get_lead_by_id(self, lead_id: str) -> Optional[LeadRecord]:
        """Fetch single lead by UUID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    l.*,
                    e.business_problem, e.services, e.budget_tier, e.budget_raw,
                    e.urgency, e.urgency_raw, e.industry, e.missing_information,
                    e.confidence_score, e.factor_breakdown, e.explanation
                FROM leads l
                LEFT JOIN extractions e ON l.id = e.lead_id
                WHERE l.id = ?
            """, (lead_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_lead_record(row)

    def update_category_override(
        self,
        lead_id: str,
        new_category: str,
        auditor: str = "human_reviewer",
        reason: str = "Manual auditor correction"
    ) -> bool:
        """
        Record a manual correction to a lead's classified category and log audit trail.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch existing override / services
            cursor.execute("SELECT manual_category_override, status FROM leads WHERE id = ?", (lead_id,))
            lead_row = cursor.fetchone()
            if not lead_row:
                return False

            old_override = lead_row["manual_category_override"]

            # Update lead
            cursor.execute("""
                UPDATE leads
                SET manual_category_override = ?, last_audit_timestamp = ?, status = 'REVIEWED'
                WHERE id = ?
            """, (new_category, now, lead_id))

            # Log audit
            cursor.execute("""
                INSERT INTO audit_logs (lead_id, timestamp, field_name, old_value, new_value, auditor, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (lead_id, now, "category", old_override or "None", new_category, auditor, reason))

            conn.commit()
            return True

    def update_lead_status(self, lead_id: str, new_status: LeadStatus) -> bool:
        """Update operational lead status (e.g. QUALIFIED, CONTACTED)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE leads SET status = ? WHERE id = ?
            """, (new_status.value, lead_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_audit_logs(self, lead_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if lead_id:
                cursor.execute("SELECT * FROM audit_logs WHERE lead_id = ? ORDER BY timestamp DESC", (lead_id,))
            else:
                cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def export_to_dataframe(self) -> pd.DataFrame:
        """Convert all leads to a flattened pandas DataFrame for UI and CSV export."""
        leads = self.get_all_leads()
        data = []
        for l in leads:
            data.append({
                "Lead ID": l.id,
                "Timestamp": l.created_at,
                "Company": l.company_name or "N/A",
                "Contact Name": l.sender_name or "N/A",
                "Email": l.sender_email or "N/A",
                "Status": l.status.value,
                "Priority Score": l.priority_score,
                "Priority Tier": l.priority_tier.value,
                "Assigned Category": l.manual_category_override or ", ".join(s.value for s in l.extracted.services),
                "Category Override": l.manual_category_override or "None",
                "Budget Tier": l.extracted.budget_tier.value,
                "Urgency": l.extracted.urgency.value,
                "Industry": l.extracted.industry,
                "Confidence": l.extracted.confidence_score,
                "Processing Mode": l.processing_mode.value,
                "Injection Detected": "YES" if l.injection_detected else "NO",
                "Summary": l.summary,
                "Raw Text": l.raw_text,
            })
        return pd.DataFrame(data)

    def _row_to_lead_record(self, row: sqlite3.Row) -> Optional[LeadRecord]:
        """Deserialize an SQLite join row into a validated LeadRecord."""
        try:
            # Parse services
            services_raw = json.loads(row["services"]) if row["services"] else []
            services: List[CynbitServiceOffering] = []
            for s in services_raw:
                try:
                    services.append(CynbitServiceOffering(s))
                except ValueError:
                    services.append(CynbitServiceOffering.UNSUPPORTED_IRRELEVANT)

            if not services:
                services = [CynbitServiceOffering.UNSUPPORTED_IRRELEVANT]

            extracted = ExtractedLead(
                business_problem=row["business_problem"] or "No problem description",
                services=services,
                budget_tier=BudgetTier(row["budget_tier"]) if row["budget_tier"] else BudgetTier.UNSPECIFIED,
                budget_raw=row["budget_raw"],
                urgency=UrgencyLevel(row["urgency"]) if row["urgency"] else UrgencyLevel.UNSPECIFIED,
                urgency_raw=row["urgency_raw"],
                industry=row["industry"] or "General Commercial",
                missing_information=json.loads(row["missing_information"]) if row["missing_information"] else [],
                confidence_score=float(row["confidence_score"] or 0.5),
            )

            # Factor breakdown
            fb_dict = json.loads(row["factor_breakdown"]) if row["factor_breakdown"] else {}
            factor_breakdown = FactorBreakdown(
                urgency_score=fb_dict.get("urgency_score", 0.0),
                budget_score=fb_dict.get("budget_score", 0.0),
                service_fit_score=fb_dict.get("service_fit_score", 0.0),
                completeness_score=fb_dict.get("completeness_score", 0.0),
            )

            return LeadRecord(
                id=row["id"],
                created_at=row["created_at"],
                content_hash=row["content_hash"],
                raw_text=row["raw_text"],
                sender_name=row["sender_name"],
                sender_email=row["sender_email"],
                company_name=row["company_name"],
                source=row["source"],
                status=LeadStatus(row["status"]) if row["status"] else LeadStatus.NEW,
                extracted=extracted,
                priority_score=float(row["priority_score"]),
                priority_tier=PriorityTier(row["priority_tier"]),
                factor_breakdown=factor_breakdown,
                explanation=row["explanation"] or "",
                summary=row["summary"],
                follow_up_questions=json.loads(row["follow_up_questions"]) if row["follow_up_questions"] else [],
                draft_reply=row["draft_reply"],
                processing_mode=ProcessingMode(row["processing_mode"]),
                injection_detected=bool(row["injection_detected"]),
                validation_warnings=json.loads(row["validation_warnings"]) if row["validation_warnings"] else [],
                manual_category_override=row["manual_category_override"],
                last_audit_timestamp=row["last_audit_timestamp"],
            )
        except Exception as e:
            print(f"Error parsing database row: {e}")
            return None
