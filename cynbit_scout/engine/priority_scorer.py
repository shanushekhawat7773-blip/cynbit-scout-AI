"""
Transparent and explainable priority scoring engine for Cynbit Scout.
Implements deterministic multi-factor weighting with per-component breakdowns.
Zero black-box logic.
"""

from typing import Tuple

from cynbit_scout.models.schemas import (
    BudgetTier,
    CynbitServiceOffering,
    ExtractedLead,
    FactorBreakdown,
    PriorityTier,
    ScoredLead,
    UrgencyLevel,
)


class PriorityScorer:
    """
    Computes an explainable commercial priority score (0-100) using explicit weights:
    - Urgency: 30%
    - Budget Clarity & Size: 25%
    - Service Fit & Alignment: 30%
    - Information Completeness: 15%
    """

    WEIGHT_URGENCY: float = 0.30
    WEIGHT_BUDGET: float = 0.25
    WEIGHT_SERVICE_FIT: float = 0.30
    WEIGHT_COMPLETENESS: float = 0.15

    HIGH_THRESHOLD: float = 75.0
    MEDIUM_THRESHOLD: float = 45.0

    def score_lead(self, extracted: ExtractedLead) -> ScoredLead:
        """
        Evaluate and score an extracted lead with mathematical transparency.
        """
        # 1. Component scores (0-100)
        s_urgency, urgency_reason = self._score_urgency(extracted.urgency)
        s_budget, budget_reason = self._score_budget(extracted.budget_tier)
        s_fit, fit_reason = self._score_service_fit(extracted.services)
        s_completeness, completeness_reason = self._score_completeness(extracted.missing_information)

        # 2. Weighted aggregate score
        raw_priority = (
            (self.WEIGHT_URGENCY * s_urgency) +
            (self.WEIGHT_BUDGET * s_budget) +
            (self.WEIGHT_SERVICE_FIT * s_fit) +
            (self.WEIGHT_COMPLETENESS * s_completeness)
        )
        priority_score = round(max(0.0, min(100.0, raw_priority)), 1)

        # 3. Determine priority tier
        # Special rule: If service fit is 0 (unsupported/irrelevant), tier is forced to LOW
        if CynbitServiceOffering.UNSUPPORTED_IRRELEVANT in extracted.services and len(extracted.services) == 1:
            priority_tier = PriorityTier.LOW
        elif priority_score >= self.HIGH_THRESHOLD:
            priority_tier = PriorityTier.HIGH
        elif priority_score >= self.MEDIUM_THRESHOLD:
            priority_tier = PriorityTier.MEDIUM
        else:
            priority_tier = PriorityTier.LOW

        factor_breakdown = FactorBreakdown(
            urgency_score=round(s_urgency, 1),
            budget_score=round(s_budget, 1),
            service_fit_score=round(s_fit, 1),
            completeness_score=round(s_completeness, 1),
        )

        explanation = self._generate_explanation(
            priority_score=priority_score,
            priority_tier=priority_tier,
            factor_breakdown=factor_breakdown,
            urgency_reason=urgency_reason,
            budget_reason=budget_reason,
            fit_reason=fit_reason,
            completeness_reason=completeness_reason,
        )

        return ScoredLead(
            extracted=extracted,
            priority_score=priority_score,
            priority_tier=priority_tier,
            factor_breakdown=factor_breakdown,
            explanation=explanation,
        )

    def _score_urgency(self, urgency: UrgencyLevel) -> Tuple[float, str]:
        """Compute urgency score and rationale."""
        if urgency == UrgencyLevel.IMMEDIATE:
            return 100.0, "Immediate deadline (<2 weeks) - high sales responsiveness required"
        elif urgency == UrgencyLevel.MEDIUM:
            return 70.0, "Medium delivery timeframe (1-3 months) - standard sales cycle"
        elif urgency == UrgencyLevel.LOW:
            return 40.0, "Extended timeframe (>3 months) - low immediate booking probability"
        elif urgency == UrgencyLevel.EXPLORATORY:
            return 30.0, "Exploratory / Discovery stage - requires nurturing"
        else:
            return 15.0, "Unspecified timeline - timeline must be established during discovery"

    def _score_budget(self, budget_tier: BudgetTier) -> Tuple[float, str]:
        """Compute budget score and rationale."""
        if budget_tier == BudgetTier.TIER_STRATEGIC:
            return 100.0, "Strategic tier (>$100k) - high enterprise commercial potential"
        elif budget_tier == BudgetTier.TIER_ENTERPRISE:
            return 85.0, "Enterprise tier ($25k-$100k) - strong project engagement"
        elif budget_tier == BudgetTier.TIER_GROWTH:
            return 65.0, "Growth tier ($5k-$25k) - standard professional services project"
        elif budget_tier == BudgetTier.TIER_MICRO:
            return 40.0, "Micro tier (<$5k) - lower commercial viability or pilot scope"
        else:
            return 15.0, "Unspecified budget - pricing expectations unclear"

    def _score_service_fit(self, services: list[CynbitServiceOffering]) -> Tuple[float, str]:
        """Compute service alignment score and rationale."""
        if not services or (len(services) == 1 and services[0] == CynbitServiceOffering.UNSUPPORTED_IRRELEVANT):
            return 0.0, "Zero fit: inquiry requests unsupported or non-commercial services"

        # Check offerings
        is_ai = CynbitServiceOffering.AI_AUTOMATION_AGENTS in services
        is_demo = any(s.name.startswith("DEMO_") for s in services)
        is_software = CynbitServiceOffering.SOFTWARE_DEVELOPMENT in services
        is_cloud = CynbitServiceOffering.CLOUD_DEVOPS in services
        is_marketing = CynbitServiceOffering.DIGITAL_MARKETING_SEO in services

        if is_ai or is_demo:
            base_score = 100.0
            fit_text = "Prime strategic fit (AI Automation / Proprietary Product Demo)"
        elif is_software or is_cloud:
            base_score = 90.0
            fit_text = "Core competency fit (Software Development / Cloud Engineering)"
        elif is_marketing:
            base_score = 70.0
            fit_text = "Secondary service fit (Digital Marketing & SEO)"
        else:
            base_score = 50.0
            fit_text = "Moderate alignment with service portfolio"

        # Multi-service bonus (+5, capped at 100)
        supported_count = sum(1 for s in services if s != CynbitServiceOffering.UNSUPPORTED_IRRELEVANT)
        if supported_count > 1:
            base_score = min(100.0, base_score + 5.0)
            fit_text += f" + cross-service synergy bonus ({supported_count} offerings)"

        return base_score, fit_text

    def _score_completeness(self, missing_info: list[str]) -> Tuple[float, str]:
        """Compute completeness score based on information gaps."""
        penalty_per_gap = 20.0
        missing_count = len(missing_info)
        score = max(20.0, 100.0 - (missing_count * penalty_per_gap))

        if missing_count == 0:
            return 100.0, "Complete inquiry with all key commercial attributes present"
        elif missing_count <= 2:
            return score, f"Minor information gaps ({missing_count} fields missing: {', '.join(missing_info)})"
        else:
            return score, f"High information deficiency ({missing_count} fields missing)"

    def _generate_explanation(
        self,
        priority_score: float,
        priority_tier: PriorityTier,
        factor_breakdown: FactorBreakdown,
        urgency_reason: str,
        budget_reason: str,
        fit_reason: str,
        completeness_reason: str,
    ) -> str:
        """Formulate concise, structured human explanation."""
        urgency_contrib = round(factor_breakdown.urgency_score * self.WEIGHT_URGENCY, 1)
        budget_contrib = round(factor_breakdown.budget_score * self.WEIGHT_BUDGET, 1)
        fit_contrib = round(factor_breakdown.service_fit_score * self.WEIGHT_SERVICE_FIT, 1)
        comp_contrib = round(factor_breakdown.completeness_score * self.WEIGHT_COMPLETENESS, 1)

        lines = [
            f"Overall Priority: {priority_score}/100 [{priority_tier.value}].",
            f"• Urgency ({urgency_contrib}/30 pts): {urgency_reason}.",
            f"• Budget Clarity ({budget_contrib}/25 pts): {budget_reason}.",
            f"• Service Fit ({fit_contrib}/30 pts): {fit_reason}.",
            f"• Information Completeness ({comp_contrib}/15 pts): {completeness_reason}.",
        ]
        return "\n".join(lines)
