"""
Human-in-the-loop response generation engine for Cynbit Scout.
Generates:
1. Exactly 3-sentence executive summaries.
2. 3-5 targeted clarifying follow-up questions.
3. Personalized draft email reply explicitly watermarked for human review.
"""

from typing import List, Optional

from cynbit_scout.models.schemas import (
    BudgetTier,
    CynbitServiceOffering,
    ExtractedLead,
    PriorityTier,
    RawInquiryInput,
    ScoredLead,
    UrgencyLevel,
)


class ResponseGenerator:
    """
    Synthesizes structured intelligence into human consultant deliverables.
    Enforces strict 'DRAFT - requires human approval' boundaries.
    """

    WATERMARK_HEADER = "=================================================================\n*** DRAFT - REQUIRES HUMAN APPROVAL | Cynbit Scout Lead Copilot ***\n================================================================="
    WATERMARK_FOOTER = "-----------------------------------------------------------------\n[NOTICE: This is an internal AI-generated draft. Review and edit before sending. Never auto-dispatched.]\n================================================================="

    def generate_summary(self, scored_lead: ScoredLead, inquiry: RawInquiryInput) -> str:
        """
        Produce a strict 3-sentence executive briefing.
        """
        extracted = scored_lead.extracted
        services_str = ", ".join(s.value for s in extracted.services)
        entity = inquiry.company_name or inquiry.sender_name or "A prospective client"

        # Sentence 1: Client profile and core business challenge
        s1 = f"{entity} in the {extracted.industry} sector is inquiring about {extracted.business_problem.rstrip('.')}."

        # Sentence 2: Requested capabilities and commercial attributes
        budget_disp = (
            extracted.budget_raw if extracted.budget_raw
            else (extracted.budget_tier.value if extracted.budget_tier != BudgetTier.UNSPECIFIED else "unspecified")
        )
        urgency_disp = (
            extracted.urgency_raw if extracted.urgency_raw
            else (extracted.urgency.value if extracted.urgency != UrgencyLevel.UNSPECIFIED else "unspecified")
        )
        s2 = f"The requirement spans {services_str}, indicating a {budget_disp} budget with a {urgency_disp} timeline."

        # Sentence 3: Priority qualification and recommended action
        if scored_lead.priority_tier == PriorityTier.HIGH:
            s3 = f"Qualified as HIGH priority ({scored_lead.priority_score}/100); immediate senior technical discovery call recommended."
        elif scored_lead.priority_tier == PriorityTier.MEDIUM:
            s3 = f"Categorized as MEDIUM priority ({scored_lead.priority_score}/100); send follow-up questionnaire to clarify technical prerequisites."
        else:
            s3 = f"Assessed as LOW priority ({scored_lead.priority_score}/100); qualification pending resolution of scope or commercial fit."

        return f"{s1} {s2} {s3}"

    def generate_follow_up_questions(self, extracted: ExtractedLead) -> List[str]:
        """
        Generate between 3 and 5 targeted clarifying questions tailored to missing info and scope.
        """
        questions: List[str] = []

        # 1. Address critical missing information
        if extracted.budget_tier == BudgetTier.UNSPECIFIED:
            questions.append("What target investment range or budget envelope has your team allocated for this initiative?")

        if extracted.urgency == UrgencyLevel.UNSPECIFIED:
            questions.append("What is your desired deployment timeline or key milestone date for the initial phase?")

        # 2. Service-specific technical questions
        if CynbitServiceOffering.AI_AUTOMATION_AGENTS in extracted.services:
            questions.append("Which internal tools, knowledge bases, or APIs will the AI workflow or agents need to integrate with?")

        if CynbitServiceOffering.SOFTWARE_DEVELOPMENT in extracted.services:
            questions.append("Do you have existing architectural documentation, wireframes, or specific tech stack preferences?")

        if CynbitServiceOffering.CLOUD_DEVOPS in extracted.services:
            questions.append("Which cloud provider (AWS, GCP, Azure) are you targeting, and what is your current infrastructure state?")

        if CynbitServiceOffering.DIGITAL_MARKETING_SEO in extracted.services:
            questions.append("What are your primary growth KPIs (e.g., organic traffic volume, MQL conversion, CPA targets)?")

        if CynbitServiceOffering.DEMO_CYNBIT_STUDIO in extracted.services:
            questions.append("Which programming languages and code evaluation workflows are you looking to benchmark with Cynbit Studio?")

        if CynbitServiceOffering.DEMO_TENANTEASE in extracted.services:
            questions.append("How many residential or commercial property units are currently under management in your portfolio?")

        if CynbitServiceOffering.DEMO_REVIO in extracted.services:
            questions.append("Which customer review channels (Google, Trustpilot, App Stores) are most critical for your automated reputation analytics?")

        # 3. Fallbacks if questions are fewer than 3
        generic_clarifiers = [
            "Are there existing software tools or legacy systems that this solution must interface with?",
            "Who are the key internal technical stakeholders leading this initiative on your side?",
            "What would success look like for your team 90 days after delivery?",
            "Do you have compliance, data residency, or security requirements (e.g. HIPAA, SOC2, GDPR) we should consider?",
        ]

        for q in generic_clarifiers:
            if len(questions) >= 5:
                break
            if q not in questions:
                questions.append(q)

        # Enforce exact bounds: min 3, max 5
        return questions[:5] if len(questions) >= 3 else (questions + generic_clarifiers)[:3]

    def generate_draft_reply(
        self,
        scored_lead: ScoredLead,
        inquiry: RawInquiryInput,
        follow_up_questions: List[str]
    ) -> str:
        """
        Compose personalized email draft watermarked with human-approval warnings.
        """
        extracted = scored_lead.extracted
        recipient = inquiry.sender_name or "Colleague"
        company_mention = f" at {inquiry.company_name}" if inquiry.company_name else ""
        services_list = ", ".join(s.value for s in extracted.services)

        q_formatted = "\n".join(f"  {idx + 1}. {q}" for idx, q in enumerate(follow_up_questions))

        # Check for out-of-scope / unsupported
        if CynbitServiceOffering.UNSUPPORTED_IRRELEVANT in extracted.services and len(extracted.services) == 1:
            body = f"""Hi {recipient},

Thank you for reaching out to Cynbit Technologies{company_mention}.

We reviewed your inquiry regarding "{extracted.business_problem}". At this time, our core engineering focus is dedicated to AI automation, custom software engineering, cloud infrastructure, and our proprietary enterprise SaaS platforms (Cynbit Studio, TenantEase, and Revio).

As your request falls outside our current service portfolio, we will not be able to take on this project. If your team has upcoming software or AI engineering needs in the future, please feel free to reconnect.

Best regards,
The Cynbit Technologies Solutions Team
https://cynbit.com"""
        else:
            body = f"""Hi {recipient},

Thank you for contacting Cynbit Technologies{company_mention}.

We have received your inquiry regarding {extracted.business_problem.rstrip('.')} and are excited about the opportunity to partner with your team. Our engineering team specializes in {services_list}, delivering scalable, production-grade solutions tailored to the {extracted.industry} space.

To ensure we prepare a tailored technical roadmap and accurate scope estimation for our initial discovery session, could you provide a bit more context on the following points:

{q_formatted}

Would you have 20 minutes available later this week for a brief technical discovery call? You can also reply directly with any documentation or specifications your team has prepared.

Looking forward to speaking soon.

Warm regards,
Technical Solutions Consulting
Cynbit Technologies
https://cynbit.com"""

        return f"{self.WATERMARK_HEADER}\n\n{body}\n\n{self.WATERMARK_FOOTER}"
