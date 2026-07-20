# APEX Developer Guide

**Audience:** Contributors and maintainers who work on the APEX codebase.
**Purpose:** This document provides the internal technical reference for the APEX platform — architecture philosophy, package responsibilities, runtime lifecycle, coding conventions, logging, testing, and pipeline flows.

---

## Table of Contents

- [Architecture Philosophy](#architecture-philosophy)
- [Package Dependency Graph](#package-dependency-graph)
- [bootstrap/ Package](#bootstrap-package)
- [runtime/ Package](#runtime-package)
- [Runtime Lifecycle](#runtime-lifecycle)
- [API Pipeline](#api-pipeline)
- [Notebook Pipeline](#notebook-pipeline)
- [Coding Conventions](#coding-conventions)
- [Logging System](#logging-system)
- [Testing Guide](#testing-guide)
- [Adding a New API Endpoint](#adding-a-new-api-endpoint)
- [Adding a New Inference Backend](#adding-a-new-inference-backend)

---

## Architecture Philosophy

APEX is built on four architectural principles:

**1. Strict layer separation.** Each layer communicates only with the layer directly below it. The API never imports from the engine. The notebook never imports from the model manager directly. This is enforced by design, not by linter rules.

**2. Engine-agnostic API.** The external API contract (`/v1/chat/completions`, etc.) must never change when the internal inference backend changes. Today it is Transformers. Tomorrow it may be vLLM, llama.cpp, or a custom ACRS engine. The API layer does not know which.

**3. Configuration-driven behaviour.** Runtime behaviour — model selection, authentication, API host/port, workspace path, logging level — is driven entirely by `apex.config.json`. No hardcoded values in the runtime.

**4. Fail loudly, safely.** Errors are always logged with full internal detail (for the operator) and returned as clean, structured JSON (for the client). Python tracebacks never reach the API response.

---

## Package Dependency Graph

```
notebook/APEX.ipynb
       │
       ▼
bootstrap/          (no runtime imports allowed here)
├── installer.py
├── launcher.py
├── repository_manager.py
├── dependency_manager.py
├── version_manager.py
├── migration.py
├── validator.py
└── diagnostics.py
       │
       ▼
runtime/            (core application — all subsystems)
├── config/         ← loaded first; all other packages depend on it
├── logging/        ← loaded second; all other packages use this
├── core/           ← lifecycle, health, global exception handling
├── drive/          ← Google Drive mount; optional dependency
├── memory/         ← workspace state; depends on config
├── engine/         ← inference adapters; depends on config, logging
├── model/          ← model manager; depends on engine, config
├── orchestrator/   ← coordinates all subsystems; depends on all above
├── api/            ← FastAPI server; depends on orchestrator
└── ui/             ← notebook dashboard; depends on all of the above
```

**Rule:** No package may import from a package above it in this graph. `engine/` may not import from `api/`. `api/` may not import from `ui/`.

---

## bootstrap/ Package

The bootstrap layer is responsible for environment preparation. It runs before the runtime is loaded and must not import from `runtime/`.

| Module | Responsibility |
|---|---|
| `config.py` | Repository URL, default branch, manifest file list |
| `installer.py` | Interactive or headless setup wizard |
| `launcher.py` | Configures `sys.path` and launches the runtime |
| `repository_manager.py` | `git clone` and `git pull` subprocess operations |
| `dependency_manager.py` | `pip install -r requirements.txt` automation |
| `version_manager.py` | Git tag enumeration, dev mode detection, version switching |
| `migration.py` | Config schema version migration with JSON backup |
| `validator.py` | Manifest-based repository structural validation |
| `diagnostics.py` | Pre-launch environment health checks (GPU, CUDA, disk space) |

---

## runtime/ Package

### `runtime/config/`
Loads, validates, and exposes `apex.config.json`. All configuration access in the runtime must go through this module. Provides typed dataclass representations of config blocks.

### `runtime/logging/`
Wraps Python's `logging` module with ANSI colour output, structured context injection, and configurable log levels. Every module gets a child logger via `get_logger(__name__)`.

### `runtime/core/`
System health checks, lifecycle hooks (startup, shutdown), and the global exception handler. Responsible for the `/health` endpoint data.

### `runtime/drive/`
Mounts Google Drive in Colab environments. Provides path resolution helpers for workspace persistence. Gracefully degrades to local filesystem when Drive is unavailable.

### `runtime/memory/`
- **Workspace Manager**: Manages isolated workspace contexts — each project gets its own directory, config, and history.
- **Conversation Logger**: Stores and retrieves conversation history in JSON format.
- **Symbol Indexer**: AST-based indexer for Python repositories. Powers future code-aware prompting.

### `runtime/engine/`
Inference engine abstraction layer. Contains an `InferenceEngine` base class with a uniform interface (`generate`, `embed`, `load`, `unload`). All concrete backends implement this interface:
- `TransformersEngine` — current primary backend
- `VLLMEngine` — planned
- `LlamaCppEngine` — planned

### `runtime/model/`
Model manager — selects the correct engine, handles model download via `huggingface_hub`, manages local cache, tracks loaded state, and provides the model metadata returned by `/v1/models`.

### `runtime/orchestrator/`
The runtime coordinator. On startup it initialises config → logging → drive → workspace → engine → model → API. On shutdown it gracefully terminates processes in reverse order.

### `runtime/api/`
The FastAPI server. See [API Pipeline](#api-pipeline) below and [docs/Server_API_Architecture.md](Server_API_Architecture.md).

### `runtime/ui/`
The notebook ipywidgets dashboard. See [docs/User_Interface_Architecture.md](User_Interface_Architecture.md).

---

## Runtime Lifecycle

```
STARTUP
   │
   ├─ 1. Config loaded and validated (runtime/config/)
   ├─ 2. Logger initialised (runtime/logging/)
   ├─ 3. Diagnostics run: GPU, CUDA, disk space (bootstrap/diagnostics.py)
   ├─ 4. Workspace directory created / loaded (runtime/memory/)
   ├─ 5. Google Drive mounted if in Colab (runtime/drive/)
   ├─ 6. Inference engine initialised (runtime/engine/)
   ├─ 7. Model loaded or downloaded (runtime/model/)
   ├─ 8. API server started (runtime/api/server.py → uvicorn)
   ├─ 9. Tunnel established (ngrok/cloudflare)
   └─10. Dashboard rendered (runtime/ui/)

RUNTIME
   ├─ API processes requests via queue
   ├─ Events emitted per request lifecycle
   ├─ Metrics captured per completion
   └─ Workspace state flushed periodically

SHUTDOWN
   ├─ 1. Active requests allowed to complete (or timeout)
   ├─ 2. Tunnel closed
   ├─ 3. API server stopped
   ├─ 4. Model unloaded, VRAM released
   └─ 5. Workspace state persisted to Drive
```

---

## API Pipeline

Every incoming HTTP request passes through this pipeline:

```
Incoming Request
      │
      ▼
  Middleware (CORS, request logging)
      │
      ▼
  Authentication (Bearer token / API key)
      │
      ▼
  Pydantic Validation (schemas.py)
      │
      ▼
  Event: REQUEST_CREATED (events.py)
      │
      ▼
  Request Queue (queue.py)
      │
      ▼
  Event: QUEUED → STARTED → RUNNING
      │
      ▼
  Endpoint Handler (chat.py / models.py / etc.)
      │
      ▼
  Runtime Core / Model Manager
      │
      ▼
  Serializer (serializers.py)
      │
      ▼
  Streaming (streaming.py) — if stream=True
      │
      ▼
  Event: COMPLETED / FAILED
      │
      ▼
  Metrics logged (metrics.py)
      │
      ▼
  Response → Client
```

---

## Notebook Pipeline

```
Cell: Bootstrap
  → git clone / git pull
  → pip install
  → Config validation
  → Google Drive mount
  → Workspace init

Cell: Model Load
  → apex.config.json read
  → Engine selected
  → Model downloaded or loaded from cache
  → VRAM allocated

Cell: Server Start
  → FastAPI app created (server.py)
  → Uvicorn started
  → Tunnel established
  → Public URL printed

Cell: Dashboard
  → ipywidgets rendered
  → Tab interface displayed at bottom of output

Cell: Shutdown
  → SIGTERM sent to uvicorn
  → Tunnel closed
  → Model unloaded
  → State persisted
```

---

## Coding Conventions

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full guide.

Quick reference:

- **Type hints on all signatures**
- **Google-style docstrings on all public classes and methods**
- **`get_logger(__name__)` — never bare `print()`**
- **`openai_error_response()` — never bare `HTTPException` with string messages**
- **No hardcoded config values — always read from `runtime/config/`**
- **No cross-layer imports — respect the dependency graph**

---

## Logging System

APEX uses a structured logger in `runtime/logging/`. Each module creates its own child logger:

```python
from runtime.logging import get_logger
logger = get_logger(__name__)

# Usage
logger.info("Server started", host="0.0.0.0", port=8000)
logger.warning("Low VRAM", available_gb=1.2, threshold_gb=2.0)
logger.error("Model load failed", model_id="Qwen/Qwen2.5-7B", error=str(e))
```

Log levels:
- `DEBUG` — internal state, every request detail
- `INFO` — normal operational events (startup, model load, request completed)
- `WARNING` — degraded conditions (low VRAM, slow response)
- `ERROR` — recoverable failures (bad request, missing model)
- `CRITICAL` — unrecoverable failures requiring shutdown

Secrets (API keys, HuggingFace tokens) are **never** passed to any log call.

---

## Testing Guide

```bash
# Run all tests
pytest tests/ -v

# Run with output visible
pytest tests/ -s -v

# Run specific file
pytest tests/test_api.py -v

# Run by keyword
pytest tests/ -k "chat" -v

# Run with coverage
pytest tests/ --cov=runtime --cov-report=term-missing
```

### Test Structure

```
tests/
├── test_api.py          — API endpoint integration tests
├── test_config.py       — Config loader and validation tests
├── test_engine.py       — Inference engine adapter tests
└── test_workspace.py    — Workspace memory and persistence tests
```

### Guidelines for new tests

- Use `httpx.AsyncClient` with FastAPI's `app` for API tests — do not hit real external services.
- Mock the model manager in API tests to avoid requiring a loaded model.
- Each new endpoint must have at minimum: a happy-path test and a `4xx`/`5xx` error test.
- Use descriptive test names: `test_chat_completion_streams_openai_format()`.

---

## Adding a New API Endpoint

1. Create `runtime/api/my_endpoint.py` with a FastAPI `APIRouter`.
2. Implement the endpoint function, using `openai_error_response()` for errors and `serializers.py` for responses.
3. Register the router in `runtime/api/router.py`:
   ```python
   from runtime.api import my_endpoint
   router.include_router(my_endpoint.router, tags=["My Feature"])
   ```
4. Add the endpoint to the table in `docs/API_REFERENCE.md` and `README.md`.
5. Write tests in `tests/test_api.py`.
6. Add an entry to `CHANGELOG.md` under `[Unreleased]`.

---

## Adding a New Inference Backend

1. Create `runtime/engine/my_engine.py`.
2. Implement the `InferenceEngine` base class interface: `load()`, `generate()`, `embed()`, `unload()`.
3. Register the engine in `runtime/engine/__init__.py` with a string key (e.g., `"my_engine"`).
4. Add the key as a valid value in the config schema (`runtime/config/`).
5. Document it in `docs/Model_Runtime_Architecture.md`.
6. Add tests in `tests/test_engine.py`.
7. Add an entry to `CHANGELOG.md` under `[Unreleased]`.
