"""
Deterministic rules-based extraction engine for Cynbit Scout.
Uses regex heuristics and weighted keyword ontologies to classify services,
extract commercial attributes (budget, urgency, industry), and flag missing info.
"""

import re
from typing import Dict, List, Optional, Tuple

from cynbit_scout.models.schemas import (
    BudgetTier,
    CynbitServiceOffering,
    ExtractedLead,
    RawInquiryInput,
    UrgencyLevel,
)


class RulesExtractor:
    """
    Fallback and baseline extractor operating with zero external dependencies or API keys.
    """

    # Keyword mappings for Cynbit public service offerings
    SERVICE_KEYWORDS: Dict[CynbitServiceOffering, List[str]] = {
        CynbitServiceOffering.AI_AUTOMATION_AGENTS: [
            "ai agent", "ai agents", "llm", "large language model", "copilot", "automate",
            "automation", "rag", "retrieval augmented", "langchain", "chatbot", "chat bot",
            "genai", "generative ai", "openai", "gemini", "fine-tuning", "workflow automation",
            "process automation", "ai pipeline", "intelligent assistant", "computer vision", "ocr"
        ],
        CynbitServiceOffering.SOFTWARE_DEVELOPMENT: [
            "software development", "custom software", "web application", "web app", "mobile app",
            "full stack", "full-stack", "backend", "frontend", "api integration", "api development",
            "saas platform", "react", "next.js", "django", "fastapi", "node.js", "database design",
            "build an app", "custom platform", "portal development"
        ],
        CynbitServiceOffering.CLOUD_DEVOPS: [
            "cloud", "aws", "amazon web services", "azure", "gcp", "google cloud", "devops",
            "docker", "kubernetes", "k8s", "terraform", "ci/cd", "ci cd", "pipeline", "infrastructure",
            "cloud migration", "serverless", "microservices", "site reliability", "sre", "monitoring"
        ],
        CynbitServiceOffering.DIGITAL_MARKETING_SEO: [
            "seo", "search engine optimization", "organic traffic", "digital marketing", "google ads",
            "ppc", "pay per click", "content marketing", "social media marketing", "conversion rate",
            "cro", "ad campaign", "brand awareness", "email marketing", "keyword ranking"
        ],
        CynbitServiceOffering.DEMO_CYNBIT_STUDIO: [
            "cynbit studio", "studio demo", "code evaluation", "code eval", "code assessment",
            "developer evaluation", "technical assessment tool", "ai code review", "studio product"
        ],
        CynbitServiceOffering.DEMO_TENANTEASE: [
            "tenantease", "tenant ease", "proptech", "tenant portal", "property management software",
            "lease management", "rent collection", "tenantease demo", "property management platform"
        ],
        CynbitServiceOffering.DEMO_REVIO: [
            "revio", "review management", "customer reviews", "reputation management",
            "feedback analytics", "review intelligence", "revio demo", "customer feedback ai"
        ],
        CynbitServiceOffering.UNSUPPORTED_IRRELEVANT: [
            "plumbing", "pipe repair", "water leak", "roof repair", "dental clinic", "teeth whitening",
            "dentist", "car mechanic", "auto repair", "brake repair", "haircut", "salon appointment",
            "personal loan", "mortgage advice", "crypto trading bot", "forex signals", "pump and dump",
            "homework help", "write my essay", "gym membership", "personal trainer", "pest control"
        ]
    }

    # Industry identification keywords
    INDUSTRY_PATTERNS: List[Tuple[str, List[str]]] = [
        ("PropTech / Real Estate", ["real estate", "property", "tenant", "landlord", "leasing", "apartment", "realty"]),
        ("FinTech / Banking", ["fintech", "banking", "payment", "crypto", "trading", "investment", "wealth", "lending"]),
        ("Healthcare / HealthTech", ["healthcare", "healthtech", "clinic", "hospital", "patient", "medical", "doctor", "telehealth"]),
        ("E-Commerce / Retail", ["ecommerce", "e-commerce", "retail", "store", "shopify", "cart", "catalog", "merchandise"]),
        ("LegalTech", ["legal", "law firm", "contract", "compliance", "litigation", "attorney"]),
        ("EdTech / Education", ["edtech", "education", "school", "university", "student", "learning", "course"]),
        ("Logistics & Supply Chain", ["logistics", "freight", "warehouse", "supply chain", "shipping", "fleet", "inventory"]),
        ("Manufacturing & Industrial", ["manufacturing", "factory", "plant", "assembly", "iot", "machinery"]),
    ]

    def extract(self, inquiry: RawInquiryInput) -> ExtractedLead:
        """
        Execute deterministic rule-based entity extraction.
        """
        text = inquiry.raw_text
        lower_text = text.lower()

        # 1. Classify Services (Multi-label)
        matched_services = self._classify_services(lower_text)

        # 2. Extract Budget
        budget_tier, budget_raw = self._extract_budget(lower_text)

        # 3. Extract Urgency
        urgency, urgency_raw = self._extract_urgency(lower_text)

        # 4. Extract Industry
        industry = self._extract_industry(lower_text)

        # 5. Extract Concise Problem Summary
        business_problem = self._extract_business_problem(text, matched_services)

        # 6. Identify Missing Information
        missing_info = self._identify_missing_information(
            inquiry=inquiry,
            budget_tier=budget_tier,
            urgency=urgency,
            business_problem=business_problem,
            services=matched_services
        )

        # 7. Confidence Score (deterministic)
        confidence = self._compute_confidence(matched_services, budget_tier, urgency, missing_info)

        return ExtractedLead(
            business_problem=business_problem,
            services=matched_services,
            budget_tier=budget_tier,
            budget_raw=budget_raw,
            urgency=urgency,
            urgency_raw=urgency_raw,
            industry=industry,
            missing_information=missing_info,
            confidence_score=confidence
        )

    def _classify_services(self, lower_text: str) -> List[CynbitServiceOffering]:
        """Match weighted keywords for all Cynbit offerings."""
        scores: Dict[CynbitServiceOffering, int] = {svc: 0 for svc in CynbitServiceOffering}

        for service, keywords in self.SERVICE_KEYWORDS.items():
            for kw in keywords:
                # Use word boundary where appropriate
                pattern = r"\b" + re.escape(kw) + r"\b"
                matches = len(re.findall(pattern, lower_text))
                if matches > 0:
                    # Give higher weight to exact product demo phrases
                    weight = 3 if service.name.startswith("DEMO_") else 1
                    scores[service] += matches * weight

        # If unsupported keywords dominate, flag as unsupported
        if scores[CynbitServiceOffering.UNSUPPORTED_IRRELEVANT] >= 1 and all(
            scores[s] == 0 for s in CynbitServiceOffering if s != CynbitServiceOffering.UNSUPPORTED_IRRELEVANT
        ):
            return [CynbitServiceOffering.UNSUPPORTED_IRRELEVANT]

        # Select all services with score > 0, ordered by score descending
        selected = [s for s, sc in scores.items() if sc > 0 and s != CynbitServiceOffering.UNSUPPORTED_IRRELEVANT]
        selected.sort(key=lambda s: scores[s], reverse=True)

        if not selected:
            # Fallback if no specific keyword matched:
            # If text has general software intent, default to software dev; otherwise unsupported/irrelevant
            if any(term in lower_text for term in ["build", "develop", "system", "platform", "tool", "website"]):
                return [CynbitServiceOffering.SOFTWARE_DEVELOPMENT]
            return [CynbitServiceOffering.UNSUPPORTED_IRRELEVANT]

        return selected

    def _extract_budget(self, text: str) -> Tuple[BudgetTier, Optional[str]]:
        """Extract explicit budget mentions and map to BudgetTier."""
        # Check high value patterns (>$100k)
        if re.search(r"(\$|usd\s*|inr\s*|rs\.?\s*)?(?:100[kK]|1[0-9]{2}[kK]|\b[1-9][0-9]{5,}\b|enterprise|strategic)", text):
            # check if explicitly >100k
            m = re.search(r"\$?\s*(?:1[0-9]{2}|[2-9][0-9]{2})[kK]", text)
            if m:
                return BudgetTier.TIER_STRATEGIC, m.group(0)

        # Check $25k-$100k patterns
        m = re.search(r"\$?\s*(?:2[5-9]|[3-9][0-9]|100)[kK]|\$?\s*(?:2[5-9],[0-9]{3}|[3-9][0-9],[0-9]{3}|100,000)", text)
        if m:
            return BudgetTier.TIER_ENTERPRISE, m.group(0)

        # Check $5k-$25k patterns
        m = re.search(r"\$?\s*(?:[5-9]|1[0-9]|2[0-4])[kK]|\$?\s*(?:[5-9],[0-9]{3}|1[0-9],[0-9]{3}|2[0-4],[0-9]{3})", text)
        if m:
            return BudgetTier.TIER_GROWTH, m.group(0)

        # Check <$5k patterns
        m = re.search(r"\$?\s*(?:[1-4])[kK]|\$?\s*[1-4],[0-9]{3}|\$?\s*[1-9][0-9]{2}\b", text)
        if m:
            return BudgetTier.TIER_MICRO, m.group(0)

        # Descriptive qualifiers
        if any(term in text for term in ["large budget", "well-funded", "series a", "series b", "enterprise budget"]):
            return BudgetTier.TIER_ENTERPRISE, "enterprise budget (qualitative)"
        if any(term in text for term in ["small budget", "limited budget", "bootstrapped", "low budget", "tight budget"]):
            return BudgetTier.TIER_MICRO, "limited budget (qualitative)"

        return BudgetTier.UNSPECIFIED, None

    def _extract_urgency(self, text: str) -> Tuple[UrgencyLevel, Optional[str]]:
        """Extract delivery urgency and timeline signals."""
        immediate_patterns = [
            r"\basap\b", r"\burgent\b", r"\bimmediately\b", r"\bright away\b",
            r"\bwithin\s+(?:a|1|2)\s+weeks?\b", r"\bthis\s+week\b", r"\bcritical\s+deadline\b"
        ]
        for pat in immediate_patterns:
            m = re.search(pat, text)
            if m:
                return UrgencyLevel.IMMEDIATE, m.group(0)

        medium_patterns = [
            r"\b1-3\s+months?\b", r"\bnext\s+month\b", r"\bby\s+(?:q[1-4]|end\s+of\s+quarter)\b",
            r"\bwithin\s+(?:a|1|2|3)\s+months?\b", r"\bthis\s+quarter\b"
        ]
        for pat in medium_patterns:
            m = re.search(pat, text)
            if m:
                return UrgencyLevel.MEDIUM, m.group(0)

        low_patterns = [
            r"\blater\s+this\s+year\b", r"\bnext\s+year\b", r"\bin\s+(?:6|six)\s+months\b",
            r"\bno\s+rush\b", r"\bflexible\s+timeline\b"
        ]
        for pat in low_patterns:
            m = re.search(pat, text)
            if m:
                return UrgencyLevel.LOW, m.group(0)

        exploratory_patterns = [
            r"\bjust\s+exploring\b", r"\bdiscovery\b", r"\binitial\s+inquiry\b",
            r"\bfeasibility\b", r"\bgathering\s+quotes\b", r"\bchecking\s+options\b"
        ]
        for pat in exploratory_patterns:
            m = re.search(pat, text)
            if m:
                return UrgencyLevel.EXPLORATORY, m.group(0)

        return UrgencyLevel.UNSPECIFIED, None

    def _extract_industry(self, text: str) -> str:
        """Infer industry context from domain vocabulary."""
        for industry, keywords in self.INDUSTRY_PATTERNS:
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    return industry
        return "General Commercial"

    def _extract_business_problem(self, raw_text: str, services: List[CynbitServiceOffering]) -> str:
        """Synthesize a concise statement of the core business problem."""
        cleaned = " ".join(raw_text.strip().split())
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", cleaned) if len(s.strip()) > 10]

        if sentences:
            # Use the first 1-2 sentences as core problem description
            problem = ". ".join(sentences[:2])
            if not problem.endswith("."):
                problem += "."
            return problem

        service_names = ", ".join(s.value for s in services)
        return f"Prospective client requesting discovery for {service_names}."

    def _identify_missing_information(
        self,
        inquiry: RawInquiryInput,
        budget_tier: BudgetTier,
        urgency: UrgencyLevel,
        business_problem: str,
        services: List[CynbitServiceOffering]
    ) -> List[str]:
        """Detect missing critical information needed for full qualification."""
        missing: List[str] = []

        if budget_tier == BudgetTier.UNSPECIFIED:
            missing.append("Target budget or financial investment range")

        if urgency == UrgencyLevel.UNSPECIFIED:
            missing.append("Expected deployment timeline or target delivery date")

        if not inquiry.sender_email and not re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", inquiry.raw_text):
            missing.append("Direct contact email for discovery follow-up")

        if not inquiry.company_name and not inquiry.sender_name:
            missing.append("Company or stakeholder identification")

        if len(inquiry.raw_text.strip()) < 60:
            missing.append("Detailed technical requirements or current system architecture")

        if CynbitServiceOffering.DEMO_CYNBIT_STUDIO in services:
            if "language" not in inquiry.raw_text.lower() and "stack" not in inquiry.raw_text.lower():
                missing.append("Target programming languages/frameworks for Cynbit Studio evaluation")

        if CynbitServiceOffering.DEMO_TENANTEASE in services:
            if not any(k in inquiry.raw_text.lower() for k in ["units", "properties", "tenants", "doors"]):
                missing.append("Portfolio size (number of units or managed properties) for TenantEase")

        return missing

    def _compute_confidence(
        self,
        services: List[CynbitServiceOffering],
        budget_tier: BudgetTier,
        urgency: UrgencyLevel,
        missing_info: List[str]
    ) -> float:
        """Calculate deterministic extraction confidence (0.0 to 1.0)."""
        score = 0.50  # Base confidence for rule match

        # Known service match boost
        if CynbitServiceOffering.UNSUPPORTED_IRRELEVANT not in services:
            score += 0.20
        else:
            score += 0.10

        # Budget clarity boost
        if budget_tier != BudgetTier.UNSPECIFIED:
            score += 0.15

        # Urgency clarity boost
        if urgency != UrgencyLevel.UNSPECIFIED:
            score += 0.15

        # Penalty for excessive missing items
        score -= len(missing_info) * 0.05

        return round(max(0.20, min(0.95, score)), 2)
