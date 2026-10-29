"""
Security sanitizer and prompt injection guard for Cynbit Scout.
Detects adversarial manipulation, neutralizes delimiter escapes, and redacts PII in logs.
"""

import re
from typing import List, Tuple


class PromptSecurityGuard:
    """
    Analyzes untrusted user text for prompt injection, jailbreaks, and delimiter escapes.
    Provides neutralization strategies before passing payloads to LLM contexts.
    """

    # Adversarial patterns targeting system prompt override
    INJECTION_PATTERNS = [
        # Instruction overrides
        (r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", "INSTRUCTION_OVERRIDE"),
        (r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:rules|instructions?)", "INSTRUCTION_OVERRIDE"),
        (r"forget\s+(?:all\s+)?(?:previous|prior|your)\s+(?:instructions|guidelines)", "INSTRUCTION_OVERRIDE"),
        (r"override\s+system\s+prompt", "INSTRUCTION_OVERRIDE"),
        
        # Roleplay / Jailbreaks
        (r"you\s+are\s+now\s+(?:in\s+)?(?:DAN|developer|god|unrestricted)\s+mode", "JAILBREAK_ROLEPLAY"),
        (r"jailbreak", "JAILBREAK_KEYWORD"),
        (r"act\s+as\s+(?:an?\s+)?unrestricted\s+ai", "JAILBREAK_ROLEPLAY"),
        (r"pretend\s+you\s+have\s+no\s+(?:rules|filters|safety)", "JAILBREAK_ROLEPLAY"),
        
        # System prompt leakage attempts
        (r"(?:print|reveal|output|display|show|leak)\s+(?:your\s+)?(?:system\s+prompt|instructions?|initial\s+prompt)", "PROMPT_LEAKAGE"),
        (r"what\s+are\s+your\s+(?:hidden|system|original)\s+instructions?", "PROMPT_LEAKAGE"),
        
        # Delimiter escapes
        (r"<\s*/?\s*(?:system|user|assistant|instruction|user_inquiry)\s*>", "DELIMITER_INJECTION"),
        (r'"{3,}|\'{3,}', "QUOTE_DELIMITER_ESCAPE"),
        (r"<{3,}|>{3,}", "BRACKET_DELIMITER_ESCAPE"),
        
        # Exfiltration & execution attempts
        (r"(?:curl|wget)\s+https?://", "EXFILTRATION_COMMAND"),
        (r"<\s*script[^>]*>", "SCRIPT_INJECTION"),
    ]

    @classmethod
    def detect_injection(cls, text: str) -> Tuple[bool, List[str]]:
        """
        Scan text for prompt injection attempts.

        Returns:
            Tuple of (is_injection_detected, list_of_matched_categories)
        """
        matched_categories: List[str] = []
        lower_text = text.lower()

        for pattern, category in cls.INJECTION_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                if category not in matched_categories:
                    matched_categories.append(category)

        return len(matched_categories) > 0, matched_categories

    @classmethod
    def sanitize(cls, text: str) -> str:
        """
        Neutralize dangerous delimiters and characters before template injection.
        """
        # Escape explicit XML-like boundary tags
        sanitized = re.sub(r"<\s*(/?)(\w+)\s*>", r"[\1\2]", text)
        # Escape markdown backticks block delimiters
        sanitized = sanitized.replace("```", "'''")
        # Escape triple quotes
        sanitized = sanitized.replace('"""', "'''")
        # Escape angled brackets sequences
        sanitized = sanitized.replace("<<<", "[[[").replace(">>>", "]]]")
        return sanitized

    @classmethod
    def wrap_safely_for_prompt(cls, text: str) -> str:
        """
        Wraps untrusted client inquiry in a secure, immutable XML-style delimiter block.
        """
        sanitized = cls.sanitize(text)
        return (
            "<untrusted_client_inquiry>\n"
            f"{sanitized}\n"
            "</untrusted_client_inquiry>"
        )


class PIIProtector:
    """
    Prevents Personally Identifiable Information (PII) from leaking into logs.
    """

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

    @classmethod
    def mask_email(cls, email: str) -> str:
        """Mask email to preserve domain but redact user part: 'j***@example.com'."""
        if not email or "@" not in email:
            return "[INVALID_EMAIL]"
        parts = email.split("@", 1)
        user = parts[0]
        domain = parts[1]
        if len(user) <= 1:
            masked_user = "*"
        else:
            masked_user = user[0] + "***"
        return f"{masked_user}@{domain}"

    @classmethod
    def redact_pii_for_logging(cls, text: str) -> str:
        """
        Scrub email addresses and telephone numbers from log strings.
        """
        redacted = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        redacted = cls.PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
        return redacted
