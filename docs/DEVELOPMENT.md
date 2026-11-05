# APEX Developer & Contribution Guide

This guide covers local development setup, code standards, test execution, and pull request workflows.

---

## 1. Local Development Setup

### Prerequisites
- Python 3.10+ (Python 3.10, 3.11, 3.12, 3.15 tested)
- Git
- Virtual environment tool (`venv`)

### Installation Steps
```bash
# Clone the repository
git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
cd APEX

# Create and activate virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install core and development dependencies in editable mode
pip install -e ".[dev,ml,ui]"
```

---

## 2. Running Tests

APEX uses `pytest` for all unit, integration, and security tests:

```bash
# Run full test suite (104 tests)
python -m pytest -v

# Run specific test modules
python -m pytest tests/test_phase4_integration.py -v
python -m pytest tests/test_phase3_chat.py -v
python -m pytest tests/test_phase2_ui.py -v
python -m pytest tests/test_phase1_reliability.py -v
```

Before submitting changes, ensure zero git whitespace or format errors:
```bash
git diff --check
```

---

## 3. Project Directory Structure

```text
APEX/
├── bootstrap/               # Repository update, installer, and diagnostics
│   ├── dependency_manager.py # Package checking and pip installer
│   ├── diagnostics.py       # Hardware and environment checks
│   ├── installer.py         # Installation wizard
│   └── launcher.py          # Process bootstrapper
├── docs/                    # Architecture, API, and usage documentation
├── notebook/                # Primary Jupyter notebook
│   └── APEX.ipynb           # Interactive portal and Launchpad (21 cells)
├── runtime/
│   ├── api/                 # FastAPI routes, schemas, tunnel, and web interface
│   │   ├── chat.py          # OpenAI /v1/chat/completions with SSE streaming
│   │   ├── files.py         # Document upload and file retrieval
│   │   ├── file_processor.py# Text extraction and context bounding
│   │   ├── manager.py       # Deterministic process and health manager
│   │   ├── router.py        # Root router & dual-mode content negotiation
│   │   ├── server.py        # FastAPI app factory
│   │   ├── tunnel.py        # Cloudflare Quick Tunnel provider
│   │   └── web_interface.py # Single-page AI Chat application
│   ├── config/              # Configuration schemas, profiles, and presets
│   ├── core/                # Lifecycle, health monitoring, error definitions
│   ├── engine/              # Transformers and mock inference adapters
│   ├── memory/              # Conversation and workspace persistence
│   ├── model/               # Model downloading, cache, and validation
│   ├── orchestrator/        # Task queue, state machine, worker
│   └── ui/                  # Launchpad (ConfigUI), Dashboard, ChatUI widgets
├── tests/                   # Automated test suite (104 tests)
├── requirements.txt         # Core dependencies
└── pyproject.toml           # Package build definition
```

---

## 4. Code Standards & Architectural Rules

- **Notebook-First**: Any new user-facing functionality must integrate cleanly with `notebook/APEX.ipynb`.
- **No Heavy External Services**: Avoid adding mandatory databases, cloud relays, or heavy unmaintained C-extensions.
- **Fail Deterministically**: Never mark a state as `RUNNING` or `READY` without verifying the underlying service via an actual health check or inference probe.
- **Single Source of Truth**: The active model loaded by `ModelManager` is the model served across both API and Web UI.
