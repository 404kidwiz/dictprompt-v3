"""
AI Prompt Refinement Module.

Transforms raw speech transcripts into structured developer prompts.
"""

from .skills import SKILLS, Skill, classify_skill
from .templates import get_template

__all__ = ["SKILLS", "Skill", "classify_skill", "get_template"]
