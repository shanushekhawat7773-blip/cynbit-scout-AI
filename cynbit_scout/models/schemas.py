"""
Pydantic schemas and domain models for Cynbit Scout.
Enforces strict typing, enum categorization, and validation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class CynbitServiceOffering(str, Enum):
    """
    Cynbit's public offerings, plus proprietary products and out-of-scope classifier.
    """
    AI_AUTOMATION_AGENTS = "AI Automation & Agents"
    SOFTWARE_DEVELOPMENT = "Custom Software Development"
    CLOUD_DEVOPS = "Cloud & DevOps Engineering"
    DIGITAL_MARKETING_SEO = "Digital Marketing & SEO"
    DEMO_CYNBIT_STUDIO = "Product Demo: Cynbit Studio"
    DEMO_TENANTEASE = "Product Demo: TenantEase"
    DEMO_REVIO = "Product Demo: Revio"
    UNSUPPORTED_IRRELEVANT = "Unsupported / Irrelevant"


class BudgetTier(str, Enum):
    """
    Explicit budget tiers for commercial qualification.
    """
    TIER_MICRO = "<$5k"
    TIER_GROWTH = "$5k-$25k"
    TIER_ENTERPRISE = "$25k-$100k"
    TIER_STRATEGIC = ">$100k"
    UNSPECIFIED = "Unspecified"


class UrgencyLevel(str, Enum):
    """
    Urgency classification based on prospective client timeline.
    """
    IMMEDIATE = "Immediate (<2 weeks)"
    MEDIUM = "Medium (1-3 months)"
    LOW = "Low (>3 months)"
    EXPLORATORY = "Exploratory / Discovery"
    UNSPECIFIED = "Unspecified"


class PriorityTier(str, Enum):
    """
    Calculated lead priority tier.
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ProcessingMode(str, Enum):
    """
    Execution mode tracking. Critical for honesty: rule output is NEVER
    disguised as LLM output.
    """
    LLM = "LLM"
    RULES_FALLBACK = "RULES_FALLBACK"


class LeadStatus(str, Enum):
    """
    Lifecycle status of a prospective lead in the CRM pipeline.
    """
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    REVIEWED = "REVIEWED"
    DISQUALIFIED = "DISQUALIFIED"
    CONTACTED = "CONTACTED"


class RawInquiryInput(BaseModel):
    """
    Raw input received from single inquiry form or CSV row.
    """
    raw_text: str = Field(..., description="Unstructured inquiry or problem description.")
    sender_name: Optional[str] = Field(default=None, description="Prospective client contact name.")
    sender_email: Optional[str] = Field(default=None, description="Contact email address.")
    company_name: Optional[str] = Field(default=None, description="Organization or domain.")
    source: str = Field(default="single_form", description="Origin of inquiry ('single_form', 'csv_upload', 'api').")


class ExtractedLead(BaseModel):
    """
    Strict extraction schema extracted by either LLM or Rules engine.
    """
    business_problem: str = Field(
        ...,
        description="Concise description of the client's underlying business problem or goal."
    )
    services: List[CynbitServiceOffering] = Field(
        ...,
        min_length=1,
        description="One or more matched Cynbit service offerings or product demos."
    )
    budget_tier: BudgetTier = Field(
        default=BudgetTier.UNSPECIFIED,
        description="Classified budget tier."
    )
    budget_raw: Optional[str] = Field(
        default=None,
        description="Exact raw budget string if mentioned (e.g. '$15k', '50,000 USD')."
    )
    urgency: UrgencyLevel = Field(
        default=UrgencyLevel.UNSPECIFIED,
        description="Classified delivery urgency level."
    )
    urgency_raw: Optional[str] = Field(
        default=None,
        description="Exact raw urgency phrasing if present (e.g. 'ASAP', 'next month')."
    )
    industry: str = Field(
        default="General Commercial",
        description="Client industry or domain (e.g., PropTech, Healthcare, E-Commerce, Fintech)."
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="List of critical missing details needed for high-confidence qualification."
    )
    confidence_score: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Confidence score of the extraction (0.0 to 1.0)."
    )


class FactorBreakdown(BaseModel):
    """
    Transparent mathematical contribution of each priority component.
    """
    urgency_score: float = Field(..., ge=0.0, le=100.0, description="Score based on timeline urgency (30% weight).")
    budget_score: float = Field(..., ge=0.0, le=100.0, description="Score based on budget clarity & tier (25% weight).")
    service_fit_score: float = Field(..., ge=0.0, le=100.0, description="Score based on alignment with Cynbit offerings (30% weight).")
    completeness_score: float = Field(..., ge=0.0, le=100.0, description="Score based on detail and completeness (15% weight).")


class ScoredLead(BaseModel):
    """
    Extraction combined with calculated priority score and factor breakdown.
    """
    extracted: ExtractedLead
    priority_score: float = Field(..., ge=0.0, le=100.0, description="Composite weighted priority score (0-100).")
    priority_tier: PriorityTier = Field(..., description="High / Medium / Low priority category.")
    factor_breakdown: FactorBreakdown
    explanation: str = Field(..., description="Human-readable transparent explanation of the score.")


class LeadRecord(BaseModel):
    """
    Comprehensive record persisted to SQLite and exposed to the Streamlit UI.
    """
    id: str = Field(..., description="Unique UUID identifier for the lead record.")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp."
    )
    content_hash: str = Field(..., description="SHA-256 hash of raw input to prevent duplicate spam.")
    raw_text: str = Field(..., description="Original raw text submitted by the prospective client.")
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    company_name: Optional[str] = None
    source: str = "single_form"
    status: LeadStatus = LeadStatus.NEW

    # Extracted and Scored Fields
    extracted: ExtractedLead
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_tier: PriorityTier
    factor_breakdown: FactorBreakdown
    explanation: str

    # Human-in-the-Loop Intelligence
    summary: str = Field(..., description="3-sentence executive summary.")
    follow_up_questions: List[str] = Field(
        ...,
        min_length=1,
        description="3-5 targeted clarifying questions to ask the prospect."
    )
    draft_reply: str = Field(
        ...,
        description="Personalized response draft explicitly watermarked for human review."
    )

    # Operational Metadata & Audit
    processing_mode: ProcessingMode = Field(..., description="LLM or RULES_FALLBACK.")
    injection_detected: bool = Field(default=False, description="Whether prompt injection patterns were intercepted.")
    validation_warnings: List[str] = Field(default_factory=list, description="Non-fatal data quality warnings.")
    manual_category_override: Optional[str] = Field(default=None, description="Human auditor override category.")
    last_audit_timestamp: Optional[str] = None
