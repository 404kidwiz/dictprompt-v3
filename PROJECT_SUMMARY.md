# DictPrompt v3 — Project Summary

**Last Updated:** 2026-03-23
**Status:** Active Development
**Repository:** https://github.com/404kidwiz/dictprompt-v3

---

## What It Is

DictPrompt v3 is a macOS menu bar app that converts voice dictation into AI-refined prompts for developers. Speak naturally → get a structured prompt ready to paste into Claude Code, Cursor, Copilot, or Windsurf.

**Core workflow:** Record → Transcribe (Whisper) → Classify intent → Refine with AI → Copy to clipboard.

---

## Project History

| Version | Approach | Status | Issue |
|---------|----------|--------|-------|
| **v1** | rumps + CustomTkinter | ❌ Abandoned | Python 3.14 + Tk 9 GIL crashes |
| **v2** | Pure AppKit/PyObjC | ❌ Abandoned | Menu items not clickable, PyObjC issues |
| **v3** | Fork of Buzz (PyQt6) | ✅ Active | Stable foundation, working UI |

### Why We Forked Buzz

- **Buzz** is a mature, actively-maintained transcription app with 18K+ GitHub stars
- Uses **PyQt6** (stable on Python 3.11+, no GIL issues)
- Built-in **Whisper** integration (local + cloud)
- Cross-platform (macOS, Windows, Linux)
- MIT licensed

---

## What We Built (v3)

### New Modules

```
dictprompt/
├── __init__.py              # Package metadata
├── refinement/              # AI prompt refinement
│   ├── __init__.py
│   ├── skills.py            # 14 developer skill types
│   ├── templates.py         # System prompts per skill
│   └── refiner.py           # Claude/OpenAI API integration
├── integration/             # Developer integrations
│   ├── __init__.py
│   └── clipboard.py         # Cross-platform clipboard
├── history/                 # Transcript archive
│   ├── __init__.py
│   └── store.py             # SQLite + FTS search
└── ui/                      # Extended Qt components
    └── __init__.py          # (placeholder)
```

### Skill Classification System

14 developer intent types ported from v2:

| Skill | Description |
|-------|-------------|
| `bug_fix` | Debugging & error resolution |
| `feature_request` | New functionality |
| `refactor` | Code improvement |
| `code_review` | Review requests |
| `documentation` | Docs & comments |
| `test_writing` | Test creation |
| `database` | SQL/schema work |
| `api_design` | API endpoints |
| `architecture` | System design |
| `git_operation` | Version control |
| `deployment` | CI/CD & infra |
| `debugging` | Investigation |
| `learning` | Explanations |
| `general` | Catch-all default |

### AI Refinement

- **Primary:** Anthropic Claude (claude-sonnet-4-6)
- **Fallback:** OpenAI GPT-4o-mini
- **Future:** Local LLM via Ollama

### History System

- SQLite backend with full-text search (FTS5)
- Store transcripts + refined prompts
- Search across all history
- Favorite/star functionality

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| UI Framework | PyQt6 (from Buzz) |
| Transcription | OpenAI Whisper (from Buzz) |
| AI Refinement | Anthropic Claude / OpenAI |
| History Storage | SQLite + FTS5 |
| Clipboard | pbcopy (macOS), xclip (Linux), clip (Windows) |
| Build System | PyInstaller (from Buzz) |
| Python Version | 3.11+ (avoid 3.14) |

---

## Repository Structure

```
dictprompt-v3/
├── buzz/                    # Original Buzz code (upstream)
│   ├── buzz/
│   │   ├── transcriber/     # Whisper integration
│   │   ├── widgets/         # Qt UI components
│   │   └── ...
│   └── ...
├── dictprompt/              # Our extensions
│   ├── refinement/          # AI prompt refinement
│   ├── integration/         # Clipboard, hotkeys
│   ├── history/             # Transcript archive
│   └── ui/                  # Extended UI
├── main.py                  # Entry point (Buzz)
├── CLAUDE.md                # Claude Code guidance
├── PROJECT_SUMMARY.md       # This file
├── Makefile                 # Build commands
└── README.md                # Buzz README
```

---

## Upstream Sync

This repo is a fork of [Buzz](https://github.com/chidiwilliams/buzz). To sync with upstream:

```bash
git fetch upstream
git merge upstream/main
# Resolve conflicts, keeping dictprompt/ directory
```

---

## Common Commands

```bash
# Run the app
python main.py

# Run tests
uv run pytest

# Build standalone app
make build

# Install dependencies
pip install -e .
```

---

## Implementation Roadmap

### Phase 1: Foundation (Days 1-2) ✅
- [x] Fork Buzz repository
- [x] Set up development environment
- [x] Create `dictprompt/` extension directory structure
- [x] Port skill classification from v2
- [ ] Test basic transcription works

### Phase 2: AI Refinement (Days 3-5)
- [ ] Implement `PromptRefiner` class
- [ ] Implement `SkillClassifier` class
- [ ] Add API key settings UI
- [ ] Create refinement panel UI
- [ ] Wire up: transcript → classify → refine → display

### Phase 3: Integration (Days 6-7)
- [ ] Implement clipboard auto-copy
- [ ] Add global hotkey support
- [ ] (Optional) macOS accessibility injection
- [ ] Test end-to-end flow

### Phase 4: History & Polish (Days 8-10)
- [ ] Wire up history store to UI
- [ ] Add search functionality
- [ ] Settings UI for API keys
- [ ] UI polish and theming

### Phase 5: Distribution (Days 11-12)
- [ ] Build system (PyInstaller)
- [ ] Code signing
- [ ] DMG creation
- [ ] Release on GitHub

---

## Lessons Learned (v1/v2)

### What Failed

1. **Python 3.14 + Tk 9 GIL Crash**
   - Tcl 9's threaded fast path + PyObjC's NSTimer callbacks = `tcl_tstate=NULL` crash
   - Required complex monkey-patching of `after()` and `bind()`
   - Even with patches, AppKit menu items weren't clickable

2. **PyObjC Complexity**
   - Pure AppKit approach had subtle issues
   - Menu items not responding to clicks despite correct target/action setup
   - Difficult to debug without native Swift/Objective-C expertise

3. **CustomTkinter on Python 3.14**
   - CTk widgets have additional event handling that clashed with patches
   - Not designed for the GIL changes in Python 3.14

### What Worked

1. **Core audio/transcription pipeline** — Whisper integration was solid
2. **Skill classification** — 14 types covered most developer use cases
3. **System prompts per skill** — Templates produced good refinements
4. **SQLite history** — FTS search worked well

### Why v3 Will Work

1. **Buzz is proven** — 18K stars, active maintenance, real users
2. **PyQt6 is stable** — No GIL issues on Python 3.11+
3. **Minimal changes** — We add on top, not rewrite
4. **Can sync upstream** — Bug fixes flow down from Buzz

---

## Related Files

- **PRD:** `../dictprompt/PRD-v3-BUZZ-FORK.md` (in v1/v2 repo)
- **CLAUDE.md:** Project guidance for Claude Code
- **README.md:** Buzz's original readme

---

## Repositories

| Repo | Purpose | URL |
|------|---------|-----|
| dictprompt-v3 | Active development | https://github.com/404kidwiz/dictprompt-v3 |
| dictprompt | Archive (v1/v2) | https://github.com/404kidwiz/dictprompt |
| buzz | Upstream | https://github.com/chidiwilliams/buzz |

---

*Last updated: 2026-03-23*
