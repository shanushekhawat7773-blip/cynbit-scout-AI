"""
Input validation and integrity guardrails for Cynbit Scout.
Enforces size constraints, detects empty/malformed inputs, and flags duplicates.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ValidationError

from cynbit_scout.models.schemas import RawInquiryInput


class ValidationResult(BaseModel):
    """Result of validating an inquiry payload."""
    is_valid: bool
    rejection_reason: Optional[str] = None
    warnings: List[str] = []
    content_hash: str
    cleaned_text: str


class InputValidator:
    """
    Validates single inputs and batch CSV records against strict quality boundaries.
    """

    MIN_LENGTH: int = 10
    MAX_LENGTH: int = 4000
    SHORT_WARNING_THRESHOLD: int = 25

    def __init__(self, seen_hashes: Optional[Set[str]] = None):
        """
        Args:
            seen_hashes: Optional set of existing SHA-256 hashes for deduplication.
        """
        self.seen_hashes: Set[str] = seen_hashes if seen_hashes is not None else set()

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute deterministic SHA-256 hash of normalized text."""
        normalized = " ".join(text.strip().lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def validate_inquiry(self, inquiry: RawInquiryInput, check_duplicate: bool = True) -> ValidationResult:
        """
        Validate a single inquiry payload.

        Returns:
            ValidationResult with pass/fail status, warnings, and normalized hash.
        """
        raw_text = inquiry.raw_text
        warnings: List[str] = []

        # Check for None or non-string
        if not isinstance(raw_text, str):
            return ValidationResult(
                is_valid=False,
                rejection_reason="Inquiry text must be a string.",
                warnings=[],
                content_hash="",
                cleaned_text=""
            )

        cleaned_text = raw_text.strip()

        # Check for empty / whitespace-only
        if not cleaned_text:
            return ValidationResult(
                is_valid=False,
                rejection_reason="Inquiry text is empty or contains only whitespace.",
                warnings=[],
                content_hash="",
                cleaned_text=""
            )

        # Check minimum length
        if len(cleaned_text) < self.MIN_LENGTH:
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Inquiry text is too short ({len(cleaned_text)} chars). Minimum required is {self.MIN_LENGTH} characters.",
                warnings=[],
                content_hash="",
                cleaned_text=cleaned_text
            )

        # Check maximum length (prevent payload exhaustion)
        if len(cleaned_text) > self.MAX_LENGTH:
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Inquiry text exceeds maximum allowed length ({len(cleaned_text)} > {self.MAX_LENGTH} characters).",
                warnings=[],
                content_hash="",
                cleaned_text=cleaned_text
            )

        # Compute hash
        content_hash = self.compute_hash(cleaned_text)

        # Check duplicate
        if check_duplicate and content_hash in self.seen_hashes:
            return ValidationResult(
                is_valid=False,
                rejection_reason="Duplicate inquiry detected: identical submission previously received.",
                warnings=["Duplicate content"],
                content_hash=content_hash,
                cleaned_text=cleaned_text
            )

        # Warn if very short
        if len(cleaned_text) < self.SHORT_WARNING_THRESHOLD:
            warnings.append(
                f"Inquiry is unusually brief ({len(cleaned_text)} chars); extraction confidence may be low."
            )

        # Warn if gibberish / low vowel ratio / repetitive characters
        if re.search(r"(.)\1{6,}", cleaned_text):
            warnings.append("Repeated character patterns detected in inquiry.")

        # If passed and deduplication enabled, track this hash
        if check_duplicate:
            self.seen_hashes.add(content_hash)

        return ValidationResult(
            is_valid=True,
            rejection_reason=None,
            warnings=warnings,
            content_hash=content_hash,
            cleaned_text=cleaned_text
        )

    def validate_batch(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[List[Tuple[RawInquiryInput, ValidationResult]], List[Dict[str, Any]]]:
        """
        Validate a batch of inquiry dictionaries (e.g. from CSV rows).

        Returns:
            Tuple of (valid_inquiries_with_results, rejected_records_with_reasons)
        """
        valid_items: List[Tuple[RawInquiryInput, ValidationResult]] = []
        rejected_items: List[Dict[str, Any]] = []

        for idx, row in enumerate(records):
            # Normalize field names
            normalized_row = {str(k).strip().lower(): v for k, v in row.items()}

            # Extract raw inquiry text from common column aliases
            text_candidate = (
                normalized_row.get("raw_text")
                or normalized_row.get("inquiry")
                or normalized_row.get("message")
                or normalized_row.get("description")
                or normalized_row.get("text")
            )

            if not text_candidate or not isinstance(text_candidate, str) or not text_candidate.strip():
                rejected_items.append({
                    "row_index": idx,
                    "raw_data": row,
                    "reason": "Missing or empty inquiry text column (expected 'raw_text', 'inquiry', or 'message')."
                })
                continue

            # Sender metadata
            sender_name = normalized_row.get("sender_name") or normalized_row.get("name")
            sender_email = normalized_row.get("sender_email") or normalized_row.get("email")
            company_name = normalized_row.get("company_name") or normalized_row.get("company")

            try:
                inquiry = RawInquiryInput(
                    raw_text=str(text_candidate),
                    sender_name=str(sender_name) if sender_name and str(sender_name).strip() else None,
                    sender_email=str(sender_email) if sender_email and str(sender_email).strip() else None,
                    company_name=str(company_name) if company_name and str(company_name).strip() else None,
                    source="csv_upload"
                )
            except ValidationError as ve:
                rejected_items.append({
                    "row_index": idx,
                    "raw_data": row,
                    "reason": f"Pydantic validation error: {str(ve)}"
                })
                continue

            result = self.validate_inquiry(inquiry, check_duplicate=True)
            if result.is_valid:
                valid_items.append((inquiry, result))
            else:
                rejected_items.append({
                    "row_index": idx,
                    "raw_data": row,
                    "reason": result.rejection_reason,
                    "content_hash": result.content_hash
                })

        return valid_items, rejected_items
