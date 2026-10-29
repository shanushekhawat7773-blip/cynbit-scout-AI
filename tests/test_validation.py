"""
Unit tests for input validation, edge cases, and batch processing.
"""

import pytest
from cynbit_scout.models.schemas import RawInquiryInput
from cynbit_scout.security.validator import InputValidator


def test_empty_and_whitespace_rejection():
    validator = InputValidator()

    # Empty text
    inq_empty = RawInquiryInput(raw_text="")
    res_empty = validator.validate_inquiry(inq_empty)
    assert not res_empty.is_valid
    assert "empty" in res_empty.rejection_reason.lower()

    # Whitespace only
    inq_ws = RawInquiryInput(raw_text="    \n\t   ")
    res_ws = validator.validate_inquiry(inq_ws)
    assert not res_ws.is_valid
    assert "whitespace" in res_ws.rejection_reason.lower()


def test_short_and_oversized_rejection():
    validator = InputValidator()

    # Too short (<10 chars)
    inq_short = RawInquiryInput(raw_text="Help now")
    res_short = validator.validate_inquiry(inq_short)
    assert not res_short.is_valid
    assert "too short" in res_short.rejection_reason.lower()

    # Oversized (>4000 chars)
    inq_long = RawInquiryInput(raw_text="A" * 4050)
    res_long = validator.validate_inquiry(inq_long)
    assert not res_long.is_valid
    assert "exceeds maximum" in res_long.rejection_reason.lower()


def test_duplicate_inquiry_detection():
    validator = InputValidator()
    text = "We need an AI agent workflow for automating our customer support pipeline."

    inq1 = RawInquiryInput(raw_text=text, sender_name="Alice")
    res1 = validator.validate_inquiry(inq1)
    assert res1.is_valid
    assert res1.content_hash in validator.seen_hashes

    # Duplicate submission with different casing and whitespace
    text_variant = "  WE NEED AN AI AGENT WORKFLOW FOR AUTOMATING OUR CUSTOMER SUPPORT PIPELINE.  "
    inq2 = RawInquiryInput(raw_text=text_variant, sender_name="Bob")
    res2 = validator.validate_inquiry(inq2)
    assert not res2.is_valid
    assert "duplicate" in res2.rejection_reason.lower()


def test_batch_validation():
    validator = InputValidator()
    records = [
        {"raw_text": "Need a custom mobile app for our retail operations.", "email": "retail@example.com"},
        {"raw_text": "", "email": "empty@example.com"},  # Invalid: empty
        {"raw_text": "Hi", "email": "short@example.com"},  # Invalid: short
        {"raw_text": "Need a custom mobile app for our retail operations.", "email": "dup@example.com"},  # Duplicate
        {"inquiry": "Looking to migrate our AWS infrastructure to Kubernetes with CI/CD.", "name": "DevOps Lead"}
    ]

    valid, rejected = validator.validate_batch(records)
    assert len(valid) == 2  # First record and fifth record (using 'inquiry' alias)
    assert len(rejected) == 3

    assert "empty" in rejected[0]["reason"].lower()
    assert "too short" in rejected[1]["reason"].lower()
    assert "duplicate" in rejected[2]["reason"].lower()
