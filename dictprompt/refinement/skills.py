"""
skills.py — Skill-based refinement engine for dictprompt.

Classifies developer dictation into one of 14 skill categories,
builds tailored system prompts, and refines transcripts using LLMs.
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Client imports — fall back to creating clients directly if core not present
# ---------------------------------------------------------------------------
try:
    from core import _get_openai_client, _get_anthropic_client
except ImportError:
    def _get_openai_client():
        import openai
        return openai.OpenAI()

    def _get_anthropic_client():
        import anthropic
        return anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Skill patterns
# ---------------------------------------------------------------------------
SKILL_PATTERNS: dict[str, list[str]] = {
    "bug_fix": [
        r"\bfix\b", r"\bbug\b", r"\bcrash\b", r"\berror\b", r"\bbroken\b",
        r"\bfailing\b", r"\bregression\b", r"\bnot working\b", r"\bexception\b",
        r"\bbreaking\b", r"\bissue\b", r"\bdefect\b",
    ],
    "feature_request": [
        r"\badd\b", r"\bimplement\b", r"\bnew feature\b", r"\bbuild\b",
        r"\bcreate\b", r"\bintroduce\b", r"\bwould like\b", r"\benhance\b",
        r"\bneed a\b", r"\bwant to add\b", r"\bsupport for\b",
    ],
    "code_review": [
        r"\breview\b", r"\blook at\b", r"\baudit\b", r"\bfeedback\b",
        r"\bcheck\b", r"\binspect\b", r"\bevaluate\b", r"\bexamine\b",
        r"\bsuggest improvements\b", r"\bwhat do you think\b",
    ],
    "refactor": [
        r"\brefactor\b", r"\brestructure\b", r"\brewrite\b", r"\bsimplify\b",
        r"\bclean up\b", r"\bimprove\b", r"\borgani[sz]e\b", r"\bmodernize\b",
        r"\boptimi[sz]e\b", r"\bdebt\b", r"\bduplicate\b",
    ],
    "documentation": [
        r"\bdocstring\b", r"\breadme\b", r"\bdocument\b", r"\bjsdoc\b",
        r"\bcomment\b", r"\bdocs\b", r"\bapi doc\b",
        r"\bchangelog\b", r"\bwiki\b", r"\bannotate\b",
    ],
    "test_writing": [
        r"\btest\b", r"\bpytest\b", r"\bjest\b", r"\bcoverage\b", r"\bmock\b",
        r"\bunit test\b", r"\bintegration test\b", r"\be2e\b", r"\bspec\b",
        r"\bassert\b", r"\bfixture\b",
    ],
    "database_query": [
        r"\bsql\b", r"\bquery\b", r"\bdatabase\b", r"\bpostgres\b", r"\bjoin\b",
        r"\bselect\b", r"\bindex\b", r"\bmysql\b", r"\bschema\b",
        r"\bmigration\b", r"\borm\b",
    ],
    "api_design": [
        r"\bapi\b", r"\bendpoint\b", r"\brest\b", r"\bgraphql\b", r"\broute\b",
        r"\brequest\b", r"\bresponse\b", r"\bhttp\b", r"\bwebhook\b",
        r"\bopenapi\b", r"\bswagger\b",
    ],
    "architecture": [
        r"\barchitecture\b", r"\bdesign\b", r"\bsystem\b", r"\bmicroservice\b",
        r"\bpattern\b", r"\bscalable\b", r"\bcomponent\b", r"\bservice\b",
        r"\binfrastructure\b", r"\bmodule\b",
    ],
    "git_operation": [
        r"\bgit\b", r"\bcommit\b", r"\bpull request\b", r"\bbranch\b",
        r"\bmerge\b", r"\brebase\b", r"\bpr\b", r"\bpush\b",
        r"\bconflict\b", r"\bcherry.pick\b",
    ],
    "deployment": [
        r"\bdeploy\b", r"\bci.cd\b", r"\bdocker\b", r"\bkubernetes\b",
        r"\bpipeline\b", r"\brelease\b", r"\bstage\b", r"\bproduction\b",
        r"\brollback\b", r"\bcontainer\b", r"\bhelm\b",
    ],
    "debugging": [
        r"\bdebug\b", r"\btrace\b", r"\bbreakpoint\b", r"\broot cause\b",
        r"\bdiagnose\b", r"\bprofile\b", r"\bstep through\b", r"\blog\b",
        r"\bstack trace\b", r"\bperformance issue\b",
    ],
    "learning": [
        r"\bexplain\b", r"\bhow does\b", r"\bhow do\b", r"\bhow\b",
        r"\bunderstand\b", r"\bconcept\b",
        r"\bwhat is\b", r"\bwhat are\b", r"\bwhy does\b", r"\bwhy is\b",
        r"\bteach\b", r"\blearn\b", r"\boverview\b",
        r"\bintroduction\b", r"\bexample of\b", r"\bworks\b",
    ],
    "general": [],
}

# Compiled pattern cache
_COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    skill: [re.compile(p, re.IGNORECASE) for p in patterns]
    for skill, patterns in SKILL_PATTERNS.items()
}

# MD5 classification cache
_CLASSIFICATION_CACHE_MAX = 500
_CLASSIFICATION_CACHE: "OrderedDict[str, tuple[str, float]]" = OrderedDict()

# ---------------------------------------------------------------------------
# Skill system prompts
# ---------------------------------------------------------------------------
SKILL_SYSTEM_PROMPTS: dict[str, dict[str, str]] = {
    "bug_fix": {
        "_base": (
            "You are a technical writing assistant specializing in bug reports. "
            "Transform the developer's dictation into a structured bug report with these exact sections:\n\n"
            "**Bug Summary:** One clear sentence describing the problem.\n"
            "**Expected Behavior:** What should happen under normal conditions.\n"
            "**Actual Behavior:** What currently happens (the bug).\n"
            "**Steps to Reproduce:** Numbered list of exact reproduction steps.\n"
            "**Environment:** OS, language/framework versions, relevant tooling.\n"
            "**Additional Context:** Error messages, logs, screenshots needed (verbatim if provided).\n\n"
            "Infer missing sections as \"[to be filled]\". Output ONLY the structured bug report, no preamble."
        ),
        "cli": (
            "Include terminal commands, exit codes, stderr output, and shell environment variables where relevant."
        ),
        "editor": (
            "Reference file paths, line numbers, IDE-specific context, and language server errors where relevant."
        ),
        "general": "",
    },
    "feature_request": {
        "_base": (
            "You are a product/engineering assistant. Transform the dictation into a structured feature request:\n\n"
            "**User Story:** As a [user type], I want [capability] so that [benefit].\n"
            "**Acceptance Criteria:** Bulleted, testable criteria — each starts with \"Given/When/Then\" or \"Should\".\n"
            "**Technical Notes:** Architecture considerations, affected APIs, data model changes, constraints mentioned.\n"
            "**Out of Scope:** Explicitly excluded items to prevent scope creep.\n"
            "**Open Questions:** Ambiguities requiring product/design decisions.\n\n"
            "Output ONLY the feature request."
        ),
        "cli": (
            "Acceptance criteria reference command-line syntax, flags, exit codes, and terminal output format."
        ),
        "editor": (
            "Reference file operations, keybindings, and IDE UI interactions where relevant."
        ),
        "general": "",
    },
    "code_review": {
        "_base": (
            "You are a senior engineer conducting a code review. Structure the review request as:\n\n"
            "**Review Scope:** What code/PR/commit should be reviewed.\n"
            "**Focus Areas:** Specific aspects to examine (security, performance, readability, correctness, test coverage).\n"
            "**Review Criteria:** The bar for approval (style guide, performance targets, coverage requirements).\n"
            "**Output Format:** How results should be delivered (inline comments, summary doc, severity ratings).\n"
            "**Context:** Language, framework, team conventions, related tickets.\n\n"
            "Output ONLY the structured review request."
        ),
        "cli": (
            "Include linting tools, static analysis commands, and CI check names."
        ),
        "editor": (
            "Reference file paths, diff views, and IDE review tool conventions."
        ),
        "general": "",
    },
    "refactor": {
        "_base": (
            "You are a software architecture assistant. Structure the refactoring request as:\n\n"
            "**Refactoring Target:** Exact class/module/function/file to refactor.\n"
            "**Current Problem:** Why the current code is problematic (coupling, complexity, duplication, performance).\n"
            "**Refactoring Goal:** The desired end state after refactoring.\n"
            "**Constraints:** Must not break X, must maintain Y API, performance bounds.\n"
            "**Design Patterns:** Patterns to apply or avoid (DRY, SOLID, strategy, factory, etc.).\n"
            "**Success Criteria:** How to verify the refactoring succeeded (tests pass, metrics improved).\n\n"
            "Output ONLY the structured refactoring request."
        ),
        "cli": (
            "Reference command-line interfaces that must remain backward-compatible."
        ),
        "editor": (
            "Reference file structure, import paths, and module boundaries."
        ),
        "general": "",
    },
    "documentation": {
        "_base": (
            "You are a technical documentation specialist. Structure the documentation request as:\n\n"
            "**Documentation Target:** What needs to be documented (function, class, module, API, system).\n"
            "**Documentation Format:** Docstrings (Google/NumPy/reST style), README, JSDoc, OpenAPI spec, wiki page.\n"
            "**Target Audience:** Who will read this (junior devs, API consumers, end users, ops team).\n"
            "**Required Sections:** List of sections that must be included.\n"
            "**Examples Needed:** Whether code examples, usage patterns, or tutorials are required.\n"
            "**Existing Docs:** Location of related docs to maintain consistency with.\n\n"
            "Output ONLY the documentation request."
        ),
        "cli": (
            "Focus on man-page style, --help output, and flag descriptions."
        ),
        "editor": (
            "Include docstring placement, hover documentation, and IDE tooltip format."
        ),
        "general": "",
    },
    "test_writing": {
        "_base": (
            "You are a test engineering specialist. Structure the test-writing request as:\n\n"
            "**Test Target:** Exact function/class/module/component to test.\n"
            "**Testing Framework:** pytest/unittest/jest/vitest/mocha/etc. and version.\n"
            "**Coverage Requirements:** Target coverage percentage, critical paths that must be covered.\n"
            "**Test Structure:** Unit vs integration vs E2E, fixture needs, test data requirements.\n"
            "**Mocking Strategy:** What to mock (external APIs, databases, filesystem, time).\n"
            "**Edge Cases:** Boundary conditions, error paths, and race conditions to cover.\n\n"
            "Output ONLY the test request."
        ),
        "cli": (
            "Include CLI argument parsing tests, exit code verification, and stdin/stdout testing."
        ),
        "editor": (
            "Reference component rendering, user interaction simulation, and snapshot testing."
        ),
        "general": "",
    },
    "database_query": {
        "_base": (
            "You are a database engineering specialist. Structure the database request as:\n\n"
            "**Operation:** SELECT/INSERT/UPDATE/DELETE/CREATE/ALTER/migration.\n"
            "**Tables Involved:** Table names, relationships, and cardinality.\n"
            "**Query Conditions:** WHERE clauses, filters, ordering, and pagination.\n"
            "**Performance Requirements:** Expected data volume, query time budget, index usage.\n"
            "**SQL Dialect:** PostgreSQL/MySQL/SQLite/BigQuery/etc.\n"
            "**Transaction Requirements:** ACID requirements, isolation level, rollback conditions.\n\n"
            "Output ONLY the database request."
        ),
        "cli": (
            "Include psql/mysql CLI syntax and EXPLAIN ANALYZE output format."
        ),
        "editor": (
            "Reference ORM model names and query builder syntax."
        ),
        "general": "",
    },
    "api_design": {
        "_base": (
            "You are an API design specialist. Structure the API request as:\n\n"
            "**Endpoint(s):** HTTP method + path pattern (e.g., POST /api/v1/users/{id}/posts).\n"
            "**Request Schema:** Headers, path params, query params, and request body (JSON schema or example).\n"
            "**Response Schema:** Success response (2xx), error responses (4xx/5xx) with body examples.\n"
            "**Authentication:** Auth mechanism (Bearer token, API key, OAuth2 scope required).\n"
            "**Rate Limiting:** Requests per second/minute, quota enforcement.\n"
            "**Edge Cases:** Concurrent requests, partial failures, idempotency requirements.\n\n"
            "Output ONLY the API design request."
        ),
        "cli": (
            "Include curl examples, httpie syntax, and CLI tool integration."
        ),
        "editor": (
            "Reference OpenAPI/Swagger annotations and code generation."
        ),
        "general": "",
    },
    "architecture": {
        "_base": (
            "You are a systems architect. Structure the architecture request as:\n\n"
            "**System Overview:** One paragraph describing what this system does and its scale.\n"
            "**Components:** Key services, databases, queues, and external dependencies.\n"
            "**Data Flow:** How data moves through the system (sequence or data flow description).\n"
            "**Technology Choices:** Languages, frameworks, databases, and infrastructure with rationale.\n"
            "**Non-Functional Requirements:** Latency, throughput, availability, consistency requirements.\n"
            "**Open Architecture Questions:** Decisions requiring stakeholder input.\n\n"
            "Output ONLY the architecture request."
        ),
        "cli": (
            "Include DevOps toolchain, deployment topology, and infrastructure-as-code approach."
        ),
        "editor": (
            "Reference IDE plugins, language servers, and developer tooling integration."
        ),
        "general": "",
    },
    "git_operation": {
        "_base": (
            "You are a version control specialist. Structure the git request as:\n\n"
            "**Operation Type:** commit/PR/branch/rebase/merge/cherry-pick/tag/release.\n"
            "**Conventional Commit:** Type(scope): description — type = feat/fix/docs/refactor/test/chore/perf.\n"
            "**PR Description:** Problem solved, approach taken, testing done, screenshots if UI.\n"
            "**Changelog Entry:** User-facing description of changes in release notes style.\n"
            "**Branch Strategy:** Branching model (GitFlow/trunk-based), base branch, target branch.\n"
            "**Review Requirements:** Reviewers needed, CI requirements, merge strategy.\n\n"
            "Output ONLY the git operation request."
        ),
        "cli": (
            "Include exact git commands with flags and commit message format."
        ),
        "editor": (
            "Reference GitHub/GitLab UI and PR template sections."
        ),
        "general": "",
    },
    "deployment": {
        "_base": (
            "You are a DevOps engineer. Structure the deployment request as:\n\n"
            "**Environment:** Target environment (dev/staging/prod/DR), cloud provider, region.\n"
            "**Deployment Steps:** Ordered list of deployment actions with verification checkpoints.\n"
            "**Pre-deployment Checks:** Health checks, smoke tests, dependency versions.\n"
            "**Rollback Procedure:** Exact steps to revert if deployment fails.\n"
            "**Monitoring:** Metrics to watch post-deployment, alert thresholds, dashboard links.\n"
            "**Communication:** Teams to notify, runbook location, on-call escalation.\n\n"
            "Output ONLY the deployment request."
        ),
        "cli": (
            "Include shell commands, kubectl/helm commands, and CI/CD pipeline names."
        ),
        "editor": (
            "Reference pipeline files, Dockerfile, and infrastructure-as-code paths."
        ),
        "general": "",
    },
    "debugging": {
        "_base": (
            "You are a systematic debugging specialist. Structure the debugging request as:\n\n"
            "**Problem Statement:** Clear description of the observed incorrect behavior.\n"
            "**Reproduction:** Minimal steps or conditions to trigger the bug.\n"
            "**Hypotheses:** 3-5 possible root causes ranked by likelihood.\n"
            "**Investigation Steps:** Specific debugging actions — add logs here, check X value, run Y profiler.\n"
            "**Debugging Tools:** Relevant tools (debugger, profiler, tracing, log analysis).\n"
            "**Known Constraints:** What has already been ruled out, time/resource constraints.\n\n"
            "Output ONLY the debugging request."
        ),
        "cli": (
            "Include gdb/lldb commands, strace, dtrace, and log grep patterns."
        ),
        "editor": (
            "Reference IDE debugger breakpoints, watch expressions, and call stack navigation."
        ),
        "general": "",
    },
    "learning": {
        "_base": (
            "You are an expert technical educator. Structure the learning request as:\n\n"
            "**Concept:** The specific topic or technology to explain.\n"
            "**Depth Level:** Beginner overview / intermediate with examples / advanced deep-dive.\n"
            "**Prior Knowledge:** What the learner already knows (assumed background).\n"
            "**Output Format:** Explanation only / explanation + code examples / tutorial with exercises.\n"
            "**Key Questions:** The specific sub-questions or confusions to address.\n"
            "**Real-World Application:** How this concept applies to the learner's current project/context.\n\n"
            "Output ONLY the learning request."
        ),
        "cli": (
            "Provide shell examples, man page references, and terminal-based exploration."
        ),
        "editor": (
            "Provide IDE-runnable code examples and interactive debugging exercises."
        ),
        "general": "",
    },
    "general": {
        "_base": (
            "You are a prompt-engineering assistant. Take raw spoken-word dictation from a software developer "
            "and transform it into a clear, well-structured prompt for an AI coding assistant.\n\n"
            "Rules:\n"
            "1. Preserve the developer's INTENT exactly — never add requirements they didn't mention.\n"
            "2. Fix grammar, filler words (\"um\", \"uh\", \"like\"), and false starts.\n"
            "3. Organize the request logically: goal first, then constraints/details.\n"
            "4. Use precise technical language where the developer was vague, but only if the meaning is "
            "unambiguous from context.\n"
            "5. Keep it concise — remove redundancy but don't lose detail.\n"
            "6. Format with markdown if structure helps (bullet points, code fences).\n"
            "7. Output ONLY the refined prompt — no preamble, no commentary."
        ),
        "cli": (
            "Format the prompt for terminal-based CLI agent interaction."
        ),
        "editor": (
            "Format the prompt for IDE AI assistant with file context."
        ),
        "general": "",
    },
}

# Valid skill names
VALID_SKILLS: frozenset[str] = frozenset(SKILL_PATTERNS.keys())

# Output format instructions
_FORMAT_INSTRUCTIONS: dict[str, str] = {
    "markdown": "Format your output using Markdown with headers, bold, and code blocks where appropriate.",
    "plain": "Format your output as plain text with no Markdown syntax.",
    "bullets": "Format your output as a bulleted list.",
    "numbered": "Format your output as a numbered list.",
    "code": "Format your output primarily as a code block, with brief prose explanation if needed.",
}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _score_transcript(transcript: str) -> dict[str, int]:
    """Return the number of pattern hits for each skill."""
    scores: dict[str, int] = {}
    for skill, patterns in _COMPILED_PATTERNS.items():
        if not patterns:
            scores[skill] = 0
            continue
        hits = sum(1 for p in patterns if p.search(transcript))
        scores[skill] = hits
    return scores


def _fast_classify(transcript: str) -> tuple[str, float]:
    """
    Score the transcript against SKILL_PATTERNS and return (skill, confidence).

    Confidence = min(0.95, pattern_hit_ratio * 0.7 + dominance * 0.3)
    where:
      - pattern_hit_ratio = hits / total_patterns for the winning skill
      - dominance = winner_score / total_hits_across_all_skills (0 if no hits)
    """
    scores = _score_transcript(transcript)

    # Filter out "general" for ranking
    ranked = {k: v for k, v in scores.items() if k != "general"}
    total_hits = sum(ranked.values())

    if total_hits == 0:
        return "general", 0.5

    best_skill = max(ranked, key=lambda k: ranked[k])
    best_score = ranked[best_skill]
    total_patterns = len(SKILL_PATTERNS[best_skill])

    pattern_hit_ratio = best_score / total_patterns if total_patterns > 0 else 0.0
    dominance = best_score / total_hits if total_hits > 0 else 0.0

    confidence = min(0.95, pattern_hit_ratio * 0.7 + dominance * 0.3)
    return best_skill, confidence


def _slow_classify(transcript: str) -> tuple[str, float]:
    """
    Use gpt-4o-mini to classify the transcript into a single skill token.
    Returns (skill, 0.9) on success, falls back to fast classification on error.
    """
    skill_list = ", ".join(s for s in VALID_SKILLS if s != "general")
    system_msg = (
        f"Classify the developer request into exactly one of these categories: "
        f"{skill_list}, general. "
        "Reply with ONLY the category name, no punctuation, no explanation."
    )
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": transcript[:2000]},
            ],
            max_tokens=10,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip().lower()
        skill = raw if raw in VALID_SKILLS else "general"
        return skill, 0.9
    except Exception:
        return _fast_classify(transcript)


def classify_skill(transcript: str, fast_only: bool = False) -> tuple[str, float]:
    """
    Classify a transcript into one of 14 skill categories.

    Args:
        transcript: Raw or processed dictation text.
        fast_only: If True, skip the LLM slow path even at low confidence.

    Returns:
        (skill_name, confidence) where confidence is in [0.0, 0.95].
    """
    cache_key = hashlib.md5(transcript.encode("utf-8", errors="replace")).hexdigest()
    if cache_key in _CLASSIFICATION_CACHE:
        return _CLASSIFICATION_CACHE[cache_key]

    skill, confidence = _fast_classify(transcript)

    if not fast_only and confidence < 0.6:
        skill, confidence = _slow_classify(transcript)

    result = (skill, confidence)
    _CLASSIFICATION_CACHE[cache_key] = result
    if len(_CLASSIFICATION_CACHE) > _CLASSIFICATION_CACHE_MAX:
        _CLASSIFICATION_CACHE.popitem(last=False)  # evict oldest
    return result


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(
    skill: str,
    context: str,
    custom_instructions: str = "",
    output_format: str = "auto",
) -> str:
    """
    Build a system prompt for the given skill and context.

    Args:
        skill: One of the 14 skill names.
        context: One of "_base", "cli", "editor", "general".
        custom_instructions: Optional additional instructions appended to the prompt.
        output_format: One of "auto", "markdown", "plain", "bullets", "numbered", "code".

    Returns:
        A fully assembled system prompt string.
    """
    if skill not in SKILL_SYSTEM_PROMPTS:
        skill = "general"

    skill_prompts = SKILL_SYSTEM_PROMPTS[skill]
    base = skill_prompts.get("_base", "")
    ctx_addon = skill_prompts.get(context, "")

    parts = [base]

    if ctx_addon:
        parts.append(ctx_addon)

    if custom_instructions:
        parts.append(custom_instructions.strip())

    if output_format in _FORMAT_INSTRUCTIONS:
        parts.append(_FORMAT_INSTRUCTIONS[output_format])

    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Refinement
# ---------------------------------------------------------------------------

def refine_with_skill(
    transcript: str,
    system_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.3,
    on_token: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Refine a transcript using the given system prompt and model.

    Args:
        transcript: The raw dictation to refine.
        system_prompt: The assembled system prompt (from build_system_prompt).
        model: Model identifier. Supports "gpt-4o", "gpt-4o-mini", or any "claude-*" model.
        temperature: Sampling temperature (0.0–1.0).
        on_token: Optional callback invoked with each streamed text chunk.
                  If None, a single non-streaming call is made.

    Returns:
        The complete refined text as a string.
    """
    is_claude = model.startswith("claude-")

    if is_claude:
        return _refine_anthropic(transcript, system_prompt, model, temperature, on_token)
    else:
        return _refine_openai(transcript, system_prompt, model, temperature, on_token)


def _refine_openai(
    transcript: str,
    system_prompt: str,
    model: str,
    temperature: float,
    on_token: Optional[Callable[[str], None]],
) -> str:
    """Refine using an OpenAI model."""
    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript},
    ]

    try:
        if on_token is not None:
            collected: list[str] = []
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    on_token(delta.content)
                    collected.append(delta.content)
            return "".join(collected)
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=False,
            )
            return response.choices[0].message.content or ""
    except RuntimeError:
        raise
    except Exception as exc:
        try:
            from core import _friendly_api_error
            friendly = _friendly_api_error(exc)
            if friendly:
                raise RuntimeError(friendly) from exc
        except ImportError:
            pass
        raise


def _refine_anthropic(
    transcript: str,
    system_prompt: str,
    model: str,
    temperature: float,
    on_token: Optional[Callable[[str], None]],
) -> str:
    """Refine using an Anthropic Claude model."""
    client = _get_anthropic_client()

    try:
        if on_token is not None:
            collected: list[str] = []
            with client.messages.stream(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": transcript}],
            ) as stream:
                for text in stream.text_stream:
                    on_token(text)
                    collected.append(text)
            return "".join(collected)
        else:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": transcript}],
            )
            return response.content[0].text if response.content else ""
    except RuntimeError:
        raise
    except Exception as exc:
        try:
            from core import _friendly_api_error
            friendly = _friendly_api_error(exc)
            if friendly:
                raise RuntimeError(friendly) from exc
        except ImportError:
            pass
        raise
