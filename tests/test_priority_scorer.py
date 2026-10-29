"""
Unit tests for explainable priority scoring engine: weight verification, boundary behavior,
factor explanations, and tier thresholds.
"""

from cynbit_scout.engine.priority_scorer import PriorityScorer
from cynbit_scout.models.schemas import (
    BudgetTier,
    CynbitServiceOffering,
    ExtractedLead,
    PriorityTier,
    UrgencyLevel,
)


def test_high_priority_enterprise_lead():
    scorer = PriorityScorer()
    lead = ExtractedLead(
        business_problem="Need urgent autonomous AI copilot integration for customer operations.",
        services=[CynbitServiceOffering.AI_AUTOMATION_AGENTS],
        budget_tier=BudgetTier.TIER_STRATEGIC,  # 100 * 0.25 = 25
        urgency=UrgencyLevel.IMMEDIATE,         # 100 * 0.30 = 30
        industry="FinTech / Banking",
        missing_information=[],                # 100 * 0.15 = 15
        confidence_score=0.90
        # Service fit = 100 * 0.30 = 30
        # Total = 30 + 25 + 30 + 15 = 100.0
    )
    scored = scorer.score_lead(lead)

    assert scored.priority_score >= 90.0
    assert scored.priority_tier == PriorityTier.HIGH
    assert scored.factor_breakdown.urgency_score == 100.0
    assert scored.factor_breakdown.budget_score == 100.0
    assert scored.factor_breakdown.service_fit_score == 100.0
    assert scored.factor_breakdown.completeness_score == 100.0
    assert "Overall Priority:" in scored.explanation


def test_low_priority_unsupported_lead():
    scorer = PriorityScorer()
    lead = ExtractedLead(
        business_problem="Need a plumber for leaking office pipes.",
        services=[CynbitServiceOffering.UNSUPPORTED_IRRELEVANT],
        budget_tier=BudgetTier.UNSPECIFIED,
        urgency=UrgencyLevel.IMMEDIATE,
        industry="General Commercial",
        missing_information=["Budget", "Timeline", "Architecture"],
        confidence_score=0.40
    )
    scored = scorer.score_lead(lead)

    assert scored.priority_tier == PriorityTier.LOW
    assert scored.factor_breakdown.service_fit_score == 0.0


def test_medium_priority_lead():
    scorer = PriorityScorer()
    lead = ExtractedLead(
        business_problem="Looking for digital marketing and SEO support for our ecommerce brand.",
        services=[CynbitServiceOffering.DIGITAL_MARKETING_SEO],
        budget_tier=BudgetTier.TIER_GROWTH,     # 65 * 0.25 = 16.25
        urgency=UrgencyLevel.MEDIUM,            # 70 * 0.30 = 21.0
        industry="E-Commerce / Retail",
        missing_information=["Target KPI", "Current Analytics"], # 60 * 0.15 = 9.0
        confidence_score=0.75
        # Service fit = 70 * 0.30 = 21.0
        # Total approx 67.25 -> MEDIUM
    )
    scored = scorer.score_lead(lead)

    assert scored.priority_tier == PriorityTier.MEDIUM
    assert 45.0 <= scored.priority_score < 75.0
