"""
Prompt Refiner — Transforms raw transcripts into structured developer prompts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .skills import Skill, classify_skill
from .templates import get_template


@dataclass
class RefinementResult:
    """Result of a prompt refinement operation."""
    original: str
    refined: str
    skill: Skill
    model: str
    latency_ms: float


class PromptRefiner:
    """Refines raw transcripts into structured developer prompts using AI."""

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = provider
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or self._default_model()
        self._client = None

    def _default_model(self) -> str:
        """Get default model for provider."""
        defaults = {
            "anthropic": "claude-sonnet-4-6",
            "openai": "gpt-4o-mini",
        }
        return defaults.get(self.provider, "claude-sonnet-4-6")

    def _get_client(self):
        """Lazy-load the API client."""
        if self._client is None:
            if self.provider == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            elif self.provider == "openai":
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        return self._client

    def refine(
        self,
        transcript: str,
        skill: Optional[Skill] = None,
    ) -> RefinementResult:
        """Refine a transcript into a structured prompt.

        Args:
            transcript: Raw speech transcript
            skill: Optional skill hint (auto-detected if not provided)

        Returns:
            RefinementResult with original, refined text, and metadata
        """
        import time

        start = time.time()

        # Auto-detect skill if not provided
        if skill is None:
            skill = classify_skill(transcript)

        # Get the system prompt template for this skill
        system_prompt = get_template(skill)

        # Call the AI API
        client = self._get_client()
        refined = self._call_api(client, system_prompt, transcript)

        latency_ms = (time.time() - start) * 1000

        return RefinementResult(
            original=transcript,
            refined=refined,
            skill=skill,
            model=self.model,
            latency_ms=latency_ms,
        )

    def _call_api(self, client, system_prompt: str, transcript: str) -> str:
        """Make the API call based on provider."""
        if self.provider == "anthropic":
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": transcript}],
            )
            return response.content[0].text

        elif self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
            )
            return response.choices[0].message.content

        else:
            raise ValueError(f"Unknown provider: {self.provider}")


# Convenience function for quick refinement
def refine_prompt(transcript: str, api_key: Optional[str] = None) -> RefinementResult:
    """Quick refinement helper."""
    refiner = PromptRefiner(api_key=api_key)
    return refiner.refine(transcript)
