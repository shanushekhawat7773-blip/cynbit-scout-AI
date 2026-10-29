"""
Unit tests for deterministic rules extractor: multi-label service classification,
commercial attribute extraction (budget, urgency, industry), and missing info detection.
"""

from cynbit_scout.engine.rules_extractor import RulesExtractor
from cynbit_scout.models.schemas import (
    BudgetTier,
    CynbitServiceOffering,
    RawInquiryInput,
    UrgencyLevel,
)


def test_ai_agent_and_cloud_multi_label():
    extractor = RulesExtractor()
    inquiry = RawInquiryInput(
        raw_text="We want to build an autonomous AI agent pipeline using LLM and deploy it on AWS Kubernetes cluster ASAP with $30k budget.",
        sender_email="tech@startup.ai",
        company_name="NextGen AI"
    )
    result = extractor.extract(inquiry)

    assert CynbitServiceOffering.AI_AUTOMATION_AGENTS in result.services
    assert CynbitServiceOffering.CLOUD_DEVOPS in result.services
    assert result.budget_tier == BudgetTier.TIER_ENTERPRISE
    assert result.urgency == UrgencyLevel.IMMEDIATE
    assert result.confidence_score >= 0.70


def test_proprietary_product_demos():
    extractor = RulesExtractor()

    # Cynbit Studio
    inq_studio = RawInquiryInput(raw_text="We need a demo of Cynbit Studio for developer technical assessment and code evaluation.")
    res_studio = extractor.extract(inq_studio)
    assert CynbitServiceOffering.DEMO_CYNBIT_STUDIO in res_studio.services

    # TenantEase
    inq_tenant = RawInquiryInput(raw_text="Interested in TenantEase property management software for our residential portal.")
    res_tenant = extractor.extract(inq_tenant)
    assert CynbitServiceOffering.DEMO_TENANTEASE in res_tenant.services
    assert res_tenant.industry == "PropTech / Real Estate"

    # Revio
    inq_revio = RawInquiryInput(raw_text="Looking for a Revio demo to automate our customer reviews and feedback sentiment.")
    res_revio = extractor.extract(inq_revio)
    assert CynbitServiceOffering.DEMO_REVIO in res_revio.services


def test_unsupported_service_classification():
    extractor = RulesExtractor()
    inq_plumber = RawInquiryInput(raw_text="Need emergency plumbing repair for water pipe leak in our basement.")
    res_plumber = extractor.extract(inq_plumber)
    assert res_plumber.services == [CynbitServiceOffering.UNSUPPORTED_IRRELEVANT]

    inq_crypto = RawInquiryInput(raw_text="Build a telegram crypto trading bot for automated forex signals and pump and dump alerts.")
    res_crypto = extractor.extract(inq_crypto)
    assert res_crypto.services == [CynbitServiceOffering.UNSUPPORTED_IRRELEVANT]


def test_missing_information_detection():
    extractor = RulesExtractor()
    # Missing budget, urgency, contact email
    inq = RawInquiryInput(raw_text="We want to automate some workflow with LLM.")
    res = extractor.extract(inq)

    assert res.budget_tier == BudgetTier.UNSPECIFIED
    assert res.urgency == UrgencyLevel.UNSPECIFIED
    assert any("budget" in m.lower() for m in res.missing_information)
    assert any("timeline" in m.lower() for m in res.missing_information)
    assert any("email" in m.lower() for m in res.missing_information)
