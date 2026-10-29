"""
Provider-agnostic LLM client for Cynbit Scout.
Supports Google Gemini and OpenAI with exponential backoff retries,
strict timeout protection, schema validation, and a one-shot self-repair loop.
"""

import json
import os
import re
import time
from typing import Any, Dict, Optional, Tuple
from pydantic import ValidationError

from cynbit_scout.llm.prompts import EXTRACTION_SYSTEM_PROMPT, REPAIR_PROMPT_TEMPLATE
from cynbit_scout.models.schemas import ExtractedLead, RawInquiryInput
from cynbit_scout.security.sanitizer import PromptSecurityGuard


class LLMClient:
    """
    Manages robust LLM inference with provider switching, timeout handling,
    Pydantic schema validation, and self-repair.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        timeout_seconds: float = 8.0,
        max_retries: int = 2
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        self._active_provider: Optional[str] = None
        if self.gemini_api_key:
            self._active_provider = "gemini"
        elif self.openai_api_key:
            self._active_provider = "openai"

    def is_available(self) -> bool:
        """Check if any supported LLM provider API key is configured."""
        return self._active_provider is not None

    def get_provider_name(self) -> str:
        """Return the active provider name or 'NONE'."""
        return self._active_provider.upper() if self._active_provider else "NONE"

    def extract(self, inquiry: RawInquiryInput) -> Tuple[Optional[ExtractedLead], Optional[str]]:
        """
        Extract structured entities via LLM.

        Returns:
            Tuple of (ExtractedLead or None, error_message or None).
            If None is returned, caller should fall back to RulesExtractor.
        """
        if not self.is_available():
            return None, "No LLM API key configured (GEMINI_API_KEY or OPENAI_API_KEY)."

        # Format input with security wrapping
        wrapped_input = PromptSecurityGuard.wrap_safely_for_prompt(inquiry.raw_text)
        user_prompt = f"Analyze the following client inquiry and output strict JSON:\n{wrapped_input}"

        # 1. First Inference Attempt
        raw_output, call_err = self._call_with_retries(EXTRACTION_SYSTEM_PROMPT, user_prompt)
        if call_err or not raw_output:
            return None, f"LLM inference error: {call_err}"

        # 2. Parse and Validate Schema
        extracted, val_err = self._parse_and_validate(raw_output)
        if extracted:
            return extracted, None

        # 3. One Repair Attempt
        repair_prompt = REPAIR_PROMPT_TEMPLATE.format(
            validation_error=val_err,
            malformed_output=raw_output[:1000]
        )
        repaired_output, rep_err = self._call_with_retries(EXTRACTION_SYSTEM_PROMPT, repair_prompt)
        if repaired_output:
            repaired_lead, rep_val_err = self._parse_and_validate(repaired_output)
            if repaired_lead:
                return repaired_lead, None

        return None, f"Schema validation and repair failed: {val_err}"

    def _call_with_retries(self, system_prompt: str, user_prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Execute LLM call with exponential backoff."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if self._active_provider == "gemini":
                    return self._call_gemini(system_prompt, user_prompt)
                elif self._active_provider == "openai":
                    return self._call_openai(system_prompt, user_prompt)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(1.0 * (2 ** attempt))

        return None, last_error

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Call Google Gemini API using google-genai SDK or fallback HTTP."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            return response.text, None
        except Exception as e:
            return None, str(e)

    def _call_openai(self, system_prompt: str, user_prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Call OpenAI chat completions via requests with timeout."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds
        )
        if resp.status_code != 200:
            return None, f"OpenAI HTTP {resp.status_code}: {resp.text}"

        data = resp.json()
        return data["choices"][0]["message"]["content"], None

    def _parse_and_validate(self, text: str) -> Tuple[Optional[ExtractedLead], Optional[str]]:
        """Clean markdown markers and validate against ExtractedLead schema."""
        cleaned = text.strip()
        # Remove markdown codeblock syntax if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
            # Pydantic validation
            lead = ExtractedLead.model_validate(data)
            return lead, None
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            return None, str(e)
