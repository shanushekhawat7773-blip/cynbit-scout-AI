"""
Unified pipeline orchestrator for Cynbit Scout.
Coordinates validation -> prompt security -> LLM/Rules routing -> priority scoring -> response generation -> SQLite persistence.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from cynbit_scout.engine.priority_scorer import PriorityScorer
from cynbit_scout.engine.response_generator import ResponseGenerator
from cynbit_scout.engine.rules_extractor import RulesExtractor
from cynbit_scout.llm.client import LLMClient
from cynbit_scout.models.schemas import (
    LeadRecord,
    LeadStatus,
    PriorityTier,
    ProcessingMode,
    RawInquiryInput,
)
from cynbit_scout.security.sanitizer import PromptSecurityGuard
from cynbit_scout.security.validator import InputValidator, ValidationResult
from cynbit_scout.storage.database import DatabaseManager


class LeadIntelligencePipeline:
    """
    End-to-end execution pipeline for inbound lead processing with transparent fallback.
    """

    def __init__(
        self,
        db_path: str = "data/cynbit_scout.db",
        default_mode: str = "hybrid",
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.db = DatabaseManager(db_path=db_path)
        self.validator = InputValidator()
        self.rules_extractor = RulesExtractor()
        self.llm_client = LLMClient(gemini_api_key=gemini_api_key, openai_api_key=openai_api_key)
        self.scorer = PriorityScorer()
        self.response_generator = ResponseGenerator()
        self.default_mode = default_mode.lower()  # 'hybrid', 'llm_only', 'rules_only'

    def process_single(
        self,
        inquiry: RawInquiryInput,
        force_mode: Optional[str] = None,
        save_to_db: bool = True
    ) -> LeadRecord:
        """
        Process a single inquiry through the entire pipeline.
        """
        # 1. Validation
        validation = self.validator.validate_inquiry(inquiry, check_duplicate=False)
        if not validation.is_valid:
            raise ValueError(f"Input validation rejected inquiry: {validation.rejection_reason}")

        # 2. Prompt Security & Injection Guard
        is_injection, injection_categories = PromptSecurityGuard.detect_injection(inquiry.raw_text)
        validation_warnings = list(validation.warnings)
        if is_injection:
            validation_warnings.append(
                f"SECURITY ALERT: Intercepted prompt injection patterns: {', '.join(injection_categories)}"
            )

        # 3. Extraction Routing (Dual-Mode)
        mode = force_mode.lower() if force_mode else self.default_mode
        extracted = None
        processing_mode = ProcessingMode.RULES_FALLBACK

        if mode in ["hybrid", "llm_only"] and self.llm_client.is_available():
            extracted, llm_err = self.llm_client.extract(inquiry)
            if extracted:
                processing_mode = ProcessingMode.LLM
            else:
                if mode == "llm_only":
                    raise RuntimeError(f"LLM extraction failed in llm_only mode: {llm_err}")
                validation_warnings.append(f"LLM fallback triggered: {llm_err}")

        # Fallback to rules if LLM not executed or failed
        if extracted is None:
            extracted = self.rules_extractor.extract(inquiry)
            processing_mode = ProcessingMode.RULES_FALLBACK

        # 4. Priority Scoring (Deterministic & Explainable)
        scored = self.scorer.score_lead(extracted)

        # 5. Response & Intelligence Generation
        summary = self.response_generator.generate_summary(scored, inquiry)
        follow_up_questions = self.response_generator.generate_follow_up_questions(extracted)
        draft_reply = self.response_generator.generate_draft_reply(scored, inquiry, follow_up_questions)

        # 6. Assemble Full Lead Record
        record = LeadRecord(
            id=str(uuid.uuid4()),
            content_hash=validation.content_hash,
            raw_text=inquiry.raw_text,
            sender_name=inquiry.sender_name,
            sender_email=inquiry.sender_email,
            company_name=inquiry.company_name,
            source=inquiry.source,
            status=LeadStatus.QUALIFIED if scored.priority_tier != PriorityTier.LOW else LeadStatus.NEW,
            extracted=extracted,
            priority_score=scored.priority_score,
            priority_tier=scored.priority_tier,
            factor_breakdown=scored.factor_breakdown,
            explanation=scored.explanation,
            summary=summary,
            follow_up_questions=follow_up_questions,
            draft_reply=draft_reply,
            processing_mode=processing_mode,
            injection_detected=is_injection,
            validation_warnings=validation_warnings,
        )

        # 7. Persistence
        if save_to_db:
            self.db.save_lead(record)

        return record

    def process_batch(
        self,
        records: List[Dict[str, Any]],
        force_mode: Optional[str] = None
    ) -> Tuple[List[LeadRecord], List[Dict[str, Any]]]:
        """
        Validate and process a batch of raw CSV rows.

        Returns:
            Tuple of (successful_lead_records, rejected_rows_with_reasons)
        """
        valid_items, rejected_items = self.validator.validate_batch(records)
        processed_records: List[LeadRecord] = []

        for inquiry, val_res in valid_items:
            try:
                record = self.process_single(inquiry, force_mode=force_mode, save_to_db=True)
                processed_records.append(record)
            except Exception as e:
                rejected_items.append({
                    "raw_text": inquiry.raw_text,
                    "reason": f"Pipeline processing exception: {str(e)}"
                })

        return processed_records, rejected_items
