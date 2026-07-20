# Changelog

All notable changes to APEX are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
APEX adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- vLLM PagedAttention inference backend
- llama.cpp GGUF backend for CPU/GPU quantized inference
- Docker container image
- PyPI package distribution
- Rate limiting and request throttling
- File upload and management API (`/v1/files`)
- Image generation endpoints (`/v1/images/*`)
- Audio transcription and speech endpoints (`/v1/audio/*`)
- Vision / multimodal input processing
- ACRS (Advanced Custom Runtime System) integration

---

## [1.2.0] — 2026-07-20

### Added
- **Modular API Architecture**: Completely restructured `runtime/api/` from a monolithic `endpoints.py` into dedicated domain modules (`chat.py`, `models.py`, `completion.py`, `embeddings.py`, `health.py`, `runtime.py`, `version.py`, `streaming.py`, `serializers.py`, `errors.py`, `events.py`, `metrics.py`, `openai.py`).
- **OpenAI-Compatible API Router** (`router.py`): Central FastAPI router aggregating all sub-routers with proper tag grouping.
- **Request Lifecycle Events** (`events.py`): Full event tracking — Request Created → Validated → Queued → Started → Running → Streaming → Completed / Failed.
- **Structured Metrics Logging** (`metrics.py`): Per-request capture of latency, prompt tokens, completion tokens, GPU usage, and VRAM.
- **Server-Sent Events Utilities** (`streaming.py`): Reusable SSE generator wrapping async generators into OpenAI-compatible `data:` streams.
- **Standardised Error Responses** (`errors.py`): All API errors now return detailed OpenAI-format JSON with `message`, `type`, `code`, and `details.resolution` fields. No Python tracebacks ever exposed.
- **WebSocket Endpoint** (`/ws`): Initial WebSocket handler for future real-time streaming and event notification.
- **Stub Endpoints with Detailed Errors**: Audio, image, vision, file, and responses endpoints implemented as `501 Not Implemented` stubs with rich error messages explaining the feature status and resolution steps.
- **`assets/` Directory**: Project banner image and documentation assets.
- **Comprehensive Documentation**: README completely rewritten; all docs files expanded; new `docs/API_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/INSTALLATION.md` created.
- **GitHub Templates**: Bug report, feature request, and PR templates fully rewritten.

### Changed
- `server.py`: Updated to import from new `router.py` instead of the removed `endpoints.py`.
- All `501 Not Implemented` stub endpoints now return detailed, human-readable error messages with `error_type`, `code`, and `details.resolution` instead of bare `"Not Implemented"` strings.

### Removed
- `runtime/api/endpoints.py`: Replaced by the new modular router and domain-specific endpoint modules.

---

## [1.0.0] — 2026-07-20

### Added
- **Core Configuration System**: `apex.config.json` schema validation, workspace config loaders, Google Drive integration, and startup configuration wizard (`bootstrap/installer.py`).
- **Bootstrap Layer**: GitHub-first deployment system — `bootstrap/` package handles git clone/pull, pip dependency resolution, version tag management, config migration, and structural validation.
- **Transformers Inference Engine**: Hugging Face Transformers backend for GPU and CPU inference. Pre-configured model profiles for Qwen, DeepSeek, Gemma, and GLM.
- **OpenAI-Compatible REST API**: FastAPI server with `POST /v1/chat/completions` (streaming and non-streaming), `GET /v1/models`, `GET /health`, `GET /status`.
- **SSE Streaming**: Server-Sent Events streaming compatible with OpenAI client libraries.
- **Workspace Memory**: Workspace isolation, JSON-based conversation history logging, AST repository and codebase symbol indexer.
- **Google Drive Persistence**: Workspace state, configuration, and history stored in Google Drive for Colab session persistence.
- **Notebook Dashboard**: Lightweight `ipywidgets` control panel with tab-based interface — Runtime, Models, Workspace, Logs, Config panels.
- **Structured Logging**: Colour-coded, structured terminal logging with ANSI support.
- **Authentication**: Bearer token and API key authentication modes.
- **Tunnel Support**: ngrok and Cloudflare Tunnel integration for public HTTPS endpoints.
- **Configuration Migrations**: Automatic schema version migration with backup on startup.

---

## Version Policy

- **Major versions** (`X.0.0`): Breaking changes to the API, config schema, or runtime behaviour.
- **Minor versions** (`1.X.0`): New features that are backwards-compatible.
- **Patch versions** (`1.0.X`): Bug fixes and security patches.

See [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md) for the full release workflow.
