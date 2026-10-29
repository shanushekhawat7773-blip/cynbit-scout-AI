"""
Unit tests for SQLite storage, retrieval, manual category overrides, and audit trails.
"""

import os
import uuid
import pytest
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
from cynbit_scout.storage.database import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_cynbit_scout.db"
    return DatabaseManager(db_path=str(db_file))


def test_insert_and_retrieve_lead(temp_db):
    lead_id = str(uuid.uuid4())
    record = LeadRecord(
        id=lead_id,
        content_hash="abc123hash",
        raw_text="We need custom SaaS portal development for healthcare patients.",
        sender_name="Dr. Marcus",
        sender_email="marcus@clinic.com",
        company_name="HealthSync",
        source="single_form",
        status=LeadStatus.NEW,
        extracted=ExtractedLead(
            business_problem="Custom patient portal development",
            services=[CynbitServiceOffering.SOFTWARE_DEVELOPMENT],
            budget_tier=BudgetTier.TIER_GROWTH,
            budget_raw="$20k",
            urgency=UrgencyLevel.MEDIUM,
            urgency_raw="next month",
            industry="Healthcare / HealthTech",
            missing_information=["EHR integration specs"],
            confidence_score=0.85
        ),
        priority_score=68.5,
        priority_tier=PriorityTier.MEDIUM,
        factor_breakdown=FactorBreakdown(
            urgency_score=70.0,
            budget_score=65.0,
            service_fit_score=90.0,
            completeness_score=80.0
        ),
        explanation="Medium priority based on healthtech scope.",
        summary="HealthSync seeks custom SaaS portal development.",
        follow_up_questions=["Which EHR system must the portal sync with?"],
        draft_reply="*** DRAFT - REQUIRES HUMAN APPROVAL ***\nHello Dr. Marcus...",
        processing_mode=ProcessingMode.RULES_FALLBACK,
        injection_detected=False
    )

    # Save
    temp_db.save_lead(record)

    # Retrieve
    retrieved = temp_db.get_lead_by_id(lead_id)
    assert retrieved is not None
    assert retrieved.id == lead_id
    assert retrieved.sender_name == "Dr. Marcus"
    assert retrieved.extracted.services == [CynbitServiceOffering.SOFTWARE_DEVELOPMENT]
    assert retrieved.processing_mode == ProcessingMode.RULES_FALLBACK


def test_manual_category_override_and_audit_trail(temp_db):
    lead_id = str(uuid.uuid4())
    record = LeadRecord(
        id=lead_id,
        content_hash="hash_override_test",
        raw_text="Looking to automate reviews on our shop.",
        status=LeadStatus.NEW,
        extracted=ExtractedLead(
            business_problem="Automate reviews",
            services=[CynbitServiceOffering.AI_AUTOMATION_AGENTS],
            budget_tier=BudgetTier.UNSPECIFIED,
            urgency=UrgencyLevel.UNSPECIFIED,
            industry="General Commercial",
            missing_information=[]
        ),
        priority_score=50.0,
        priority_tier=PriorityTier.MEDIUM,
        factor_breakdown=FactorBreakdown(urgency_score=15, budget_score=15, service_fit_score=100, completeness_score=100),
        explanation="Initial score",
        summary="Summary test",
        follow_up_questions=["Q1", "Q2", "Q3"],
        draft_reply="Draft reply test",
        processing_mode=ProcessingMode.RULES_FALLBACK,
    )
    temp_db.save_lead(record)

    # Apply human override to Revio demo
    new_cat = CynbitServiceOffering.DEMO_REVIO.value
    success = temp_db.update_category_override(
        lead_id=lead_id,
        new_category=new_cat,
        auditor="senior_consultant",
        reason="Client specifically needs Revio demo"
    )
    assert success

    # Verify update in record
    updated = temp_db.get_lead_by_id(lead_id)
    assert updated.manual_category_override == new_cat
    assert updated.status == LeadStatus.REVIEWED

    # Verify audit log
    logs = temp_db.get_audit_logs(lead_id)
    assert len(logs) == 1
    assert logs[0]["field_name"] == "category"
    assert logs[0]["new_value"] == new_cat
    assert logs[0]["auditor"] == "senior_consultant"


def test_export_dataframe(temp_db):
    lead_id = str(uuid.uuid4())
    record = LeadRecord(
        id=lead_id,
        content_hash="df_export_test",
        raw_text="Cloud migration to GCP with Kubernetes.",
        status=LeadStatus.QUALIFIED,
        extracted=ExtractedLead(
            business_problem="Cloud migration",
            services=[CynbitServiceOffering.CLOUD_DEVOPS],
            budget_tier=BudgetTier.TIER_ENTERPRISE,
            urgency=UrgencyLevel.IMMEDIATE,
            industry="General Commercial",
            missing_information=[]
        ),
        priority_score=85.0,
        priority_tier=PriorityTier.HIGH,
        factor_breakdown=FactorBreakdown(urgency_score=100, budget_score=85, service_fit_score=90, completeness_score=100),
        explanation="High priority",
        summary="Summary test",
        follow_up_questions=["Q1", "Q2", "Q3"],
        draft_reply="Draft reply",
        processing_mode=ProcessingMode.LLM
    )
    temp_db.save_lead(record)

    df = temp_db.export_to_dataframe()
    assert len(df) == 1
    assert "Lead ID" in df.columns
    assert "Priority Score" in df.columns
    assert df.iloc[0]["Processing Mode"] == "LLM"
