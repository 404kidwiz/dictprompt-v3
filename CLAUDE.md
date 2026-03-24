# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DictPrompt v3 is a fork of [Buzz](https://github.com/chidiwilliams/buzz) with AI-powered prompt refinement for developers. It transcribes voice to text using Whisper and refines it into structured prompts for AI coding assistants.

## Key Commands

```bash
# Run the app
python main.py

# Run tests
uv run pytest

# Build standalone app
make build

# Sync with upstream Buzz
git fetch upstream
git merge upstream/main
```

## Architecture

```
dictprompt-v3/
├── buzz/                   # Original Buzz code (upstream)
│   ├── buzz/
│   │   ├── transcriber/    # Whisper integration
│   │   ├── widgets/        # Qt UI components
│   │   └── ...
│   └── ...
├── dictprompt/             # Our extensions
│   ├── refinement/         # AI prompt refinement
│   │   ├── skills.py       # Skill classification
│   │   ├── templates.py    # System prompts per skill
│   │   └── refiner.py      # Claude/OpenAI integration
│   ├── integration/        # Developer integrations
│   │   └── clipboard.py    # Clipboard utilities
│   ├── history/            # Transcript history
│   │   └── store.py        # SQLite backend
│   └── ui/                 # Extended UI components
├── main.py                 # Entry point
└── Makefile                # Build commands
```

## Upstream Sync

This repo is a fork of Buzz. To sync with upstream:

```bash
git fetch upstream
git merge upstream/main
# Resolve conflicts, keeping our dictprompt/ directory
```

## Development Notes

- Use `uv` for dependency management (Buzz convention)
- Python 3.11+ recommended (avoid 3.14 for stability)
- PyQt6 for UI (inherited from Buzz)
- MIT License (inherited from Buzz)

## AI Refinement Flow

1. User speaks → Whisper transcribes → Raw transcript
2. Raw transcript → Skill classifier → Detect intent (bug_fix, feature, refactor, etc.)
3. Raw transcript + Skill system prompt → Claude API → Refined prompt
4. Refined prompt → Clipboard → User pastes into IDE

## Skills

14 developer skill types: bug_fix, feature_request, refactor, code_review, documentation, test_writing, database, api_design, architecture, git_operation, deployment, debugging, learning, general
