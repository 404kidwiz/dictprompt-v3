"""
Prompt templates for dictprompt.
Stores named templates in ~/.dictprompt/templates.json
Each template has a name, system_prompt, context, and optional skill_override.
"""

import json
from pathlib import Path
from typing import TypedDict, Optional

TEMPLATES_FILE = Path.home() / ".dictprompt" / "templates.json"


class Template(TypedDict):
    name: str
    system_prompt: str
    context: str
    skill_override: str
    description: str


DEFAULT_TEMPLATES: list = [
    {
        "name": "Quick Bug Report",
        "system_prompt": (
            "Output a concise bug report: **Bug:** one sentence. "
            "**Steps:** numbered. **Expected vs Actual:** one line each. "
            "Output ONLY the report."
        ),
        "context": "general",
        "skill_override": "bug_fix",
        "description": "Fast bug report from voice",
    },
    {
        "name": "PR Description",
        "system_prompt": (
            "Write a GitHub pull request description: **What**: one sentence. "
            "**Why**: motivation. **How**: implementation approach. "
            "**Testing**: how it was tested. Output ONLY the PR description."
        ),
        "context": "general",
        "skill_override": "git_operation",
        "description": "GitHub PR description",
    },
    {
        "name": "Meeting Note",
        "system_prompt": (
            "Convert this spoken note into clean meeting notes with: "
            "**Action Items:** bulleted. **Decisions:** bulleted. "
            "**Context:** brief summary. Output ONLY the notes."
        ),
        "context": "general",
        "skill_override": "general",
        "description": "Meeting dictation to notes",
    },
]


def _ensure_dir() -> None:
    """Create ~/.dictprompt/ directory if it does not exist."""
    TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_templates() -> list:
    """Load templates from JSON file. Returns empty list on any error."""
    _ensure_dir()
    try:
        if TEMPLATES_FILE.exists():
            with TEMPLATES_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_templates(templates: list) -> None:
    """Write template list to JSON with indent=2."""
    _ensure_dir()
    with TEMPLATES_FILE.open("w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)


def save_template(t: dict) -> None:
    """Append template or update existing one by name."""
    templates = load_templates()
    for i, existing in enumerate(templates):
        if existing.get("name") == t.get("name"):
            templates[i] = t
            save_templates(templates)
            return
    templates.append(t)
    save_templates(templates)


def delete_template(name: str) -> bool:
    """Remove template by name. Returns True if found and deleted."""
    templates = load_templates()
    new_templates = [t for t in templates if t.get("name") != name]
    if len(new_templates) == len(templates):
        return False
    save_templates(new_templates)
    return True


def apply_template(
    t: dict,
    transcript: str,
    model: str = "gpt-4o",
    temperature: float = 0.3,
    on_token=None,
) -> tuple:
    """
    Run refinement using t["system_prompt"] as the system message.
    Returns (refined_text, skill_override or "general").
    """
    from core import _get_openai_client, _get_anthropic_client

    system_prompt = t.get("system_prompt", "Refine the following text.")
    skill = t.get("skill_override", "general") or "general"

    if model.startswith("claude"):
        client = _get_anthropic_client()
        messages = [{"role": "user", "content": transcript}]

        if on_token is not None:
            parts: list[str] = []
            with client.messages.stream(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    parts.append(text)
                    on_token(text)
            refined = "".join(parts)
        else:
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            )
            refined = response.content[0].text or ""
    else:
        client = _get_openai_client()
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ]

        if on_token is not None:
            stream = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=msgs,
                stream=True,
            )
            parts = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    parts.append(delta)
                    on_token(delta)
            refined = "".join(parts)
        else:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=msgs,
            )
            refined = response.choices[0].message.content or ""

    return (refined.strip(), skill)
