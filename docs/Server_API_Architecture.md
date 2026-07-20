# Server API Architecture

**Component:** `runtime/api/`
**Purpose:** This document describes the architecture of the APEX OpenAI-compatible REST API — the middleware stack, request pipeline, routing structure, authentication, streaming, error handling, and WebSocket endpoint.

---

## Purpose and Scope

The API layer is APEX's external face. Its responsibilities are:

1. Accept HTTP requests from any OpenAI-compatible client.
2. Authenticate and validate requests before any runtime processing.
3. Route requests to the correct endpoint handler.
4. Delegate actual work to the Runtime Core (model manager, workspace manager).
5. Stream or serialise responses in the exact format OpenAI clients expect.
6. Return standardised, safe error responses — never Python tracebacks.

**Invariant:** The API layer never directly loads or manages models. It communicates exclusively with `runtime/model/manager.py` and `runtime/orchestrator/`.

---

## Module Structure

```
runtime/api/
├── server.py          — FastAPI app factory, middleware registration
├── router.py          — Central APIRouter, includes all sub-routers
├── middleware.py      — CORS, request logging middleware
├── authentication.py  — Bearer token / API key verification
├── security.py        — Global exception handler, traceback suppression
├── schemas.py         — Pydantic request/response models
├── validation.py      — Extra validation utilities
├── errors.py          — openai_error_response() helper
├── events.py          — Request lifecycle event tracking
├── metrics.py         — Per-request latency, token, GPU metrics
├── streaming.py       — SSE generator utilities
├── serializers.py     — OpenAI response format builders
├── openai.py          — Constants (API version, model names)
├── queue.py           — Request queue management
│
├── health.py          — GET /health
├── runtime.py         — GET /runtime
├── version.py         — GET /version
├── models.py          — GET /v1/models, GET /v1/models/{id}
├── chat.py            — POST /v1/chat/completions
├── completion.py      — POST /v1/completions
├── embeddings.py      — POST /v1/embeddings
├── websocket.py       — WS /ws
│
├── images.py          — POST /v1/images/* (501 stub)
├── audio.py           — POST /v1/audio/* (501 stub)
├── files.py           — POST/GET/DELETE /v1/files (501 stub)
├── vision.py          — POST /v1/vision (501 stub)
└── responses.py       — POST /v1/responses (501 stub)
```

---

## FastAPI Application Lifecycle

The FastAPI application is created by `server.py`'s `create_app()` factory function:

```
create_app(config, state, auth_manager, queue, model_manager)
      │
      ├─ Register global exception handler (security.py)
      ├─ Configure CORS middleware (middleware.py)
      ├─ Register request logging middleware (middleware.py)
      ├─ Create auth dependency (authentication.py)
      ├─ Build router (router.py)
      └─ Mount router with auth dependency
```

The app is then served by `uvicorn` with the configuration from `apex.config.json`.

---

## Request Pipeline

Every HTTP request flows through this ordered pipeline:

```
Incoming HTTP Request
         │
         ▼
  ┌──────────────────┐
  │ CORS Middleware   │  — Sets Access-Control-Allow-* headers
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Request Logging   │  — Logs method, path, client IP, headers
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Authentication    │  — Verifies Bearer token or API key
  └────────┬─────────┘   — Returns 401 if auth fails (when enabled)
           │
           ▼
  ┌──────────────────┐
  │ Pydantic          │  — Validates request body against schema
  │ Validation        │  — Returns 422 with field errors if invalid
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Event Emit        │  — REQUEST_CREATED event logged
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Request Queue     │  — Queued if concurrent limit reached
  └────────┬─────────┘   — QUEUED → STARTED events emitted
           │
           ▼
  ┌──────────────────┐
  │ Endpoint Handler  │  — chat.py, models.py, embeddings.py, etc.
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Model Manager     │  — Actual inference or metadata lookup
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────────┐
  │ Serializer /          │  — OpenAI-format JSON response
  │ SSE Stream Generator  │  — or text/event-stream for streaming
  └────────┬─────────────┘
           │
           ▼
  ┌──────────────────┐
  │ Metrics Logged    │  — Latency, tokens, GPU usage
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Event: COMPLETED  │
  │ or FAILED         │
  └──────────────────┘
```

---

## Authentication

Implemented in `runtime/api/authentication.py`.

| Mode | Header | Behaviour |
|---|---|---|
| Disabled | N/A | All requests accepted |
| API Key | `Authorization: Bearer <key>` | Key compared to configured value |
| Developer Mode | N/A | Auth disabled, verbose logging |

When authentication fails, the response is always:

```json
{
  "error": {
    "message": "Authentication failed. Provide a valid Bearer token.",
    "type": "authentication_error",
    "code": "invalid_api_key",
    "details": {
      "resolution": "Pass a valid API key as 'Authorization: Bearer <key>'"
    }
  }
}
```

---

## Streaming (SSE)

**Module:** `runtime/api/streaming.py`

The `generate_sse()` utility wraps any async generator into the `text/event-stream` format that OpenAI clients expect:

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk",...}\n\n
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"Hello"}}],...}\n\n
data: [DONE]\n\n
```

Chat completions route: if `stream=True` in the request body, `chat.py` returns a `StreamingResponse` with `media_type="text/event-stream"`.

---

## Error Handling

**Module:** `runtime/api/errors.py`

All API errors use the `openai_error_response()` helper:

```python
return openai_error_response(
    message="The model is not currently loaded.",
    error_type="runtime_error",
    code="model_not_loaded",
    status_code=503,
    details={"resolution": "Load a model before sending completions requests."}
)
```

**Global exception handler** (`security.py`) catches any unhandled exceptions and returns:

```json
{
  "error": {
    "message": "An internal server error occurred.",
    "type": "internal_server_error",
    "code": "unexpected_error"
  }
}
```

Python tracebacks, file paths, and internal state are never included in API responses.

---

## Endpoint Catalogue

### Implemented

| Method | Path | Handler | Notes |
|---|---|---|---|
| `GET` | `/health` | `health.py` | System status, uptime, GPU, queue |
| `GET` | `/runtime` | `runtime.py` | VRAM, device, engine, precision |
| `GET` | `/version` | `version.py` | Runtime + API version |
| `GET` | `/v1/models` | `models.py` | List available models |
| `GET` | `/v1/models/{id}` | `models.py` | Single model details |
| `POST` | `/v1/chat/completions` | `chat.py` | OpenAI chat, streaming + non-streaming |
| `POST` | `/v1/completions` | `completion.py` | Classic text completion |
| `POST` | `/v1/embeddings` | `embeddings.py` | Text embeddings |
| `WS` | `/ws` | `websocket.py` | Real-time events and streaming |

### Stubbed (501 — Schema Ready)

| Method | Path | Handler |
|---|---|---|
| `POST` | `/v1/images/generations` | `images.py` |
| `POST` | `/v1/images/edits` | `images.py` |
| `POST` | `/v1/images/variations` | `images.py` |
| `POST` | `/v1/audio/transcriptions` | `audio.py` |
| `POST` | `/v1/audio/translations` | `audio.py` |
| `POST` | `/v1/audio/speech` | `audio.py` |
| `POST` | `/v1/files` | `files.py` |
| `GET` | `/v1/files` | `files.py` |
| `DELETE` | `/v1/files/{id}` | `files.py` |
| `POST` | `/v1/vision` | `vision.py` |
| `POST` | `/v1/images/analyze` | `vision.py` |
| `POST` | `/v1/responses` | `responses.py` |

---

## OpenAI Compatibility Notes

The following OpenAI API fields are currently accepted in request bodies but are not enforced during generation (they are validated and forwarded to the engine):

- `seed` — accepted, not yet enforced for reproducibility
- `logit_bias` — accepted, not yet enforced
- `n` — accepted; only `n=1` completions are returned currently
- `tool_choice`, `tools` — accepted in schema; function calling not yet executed

These fields are included in the schema now so clients that send them (e.g., Cline, Continue) do not receive validation errors.

---

## WebSocket Endpoint

**Module:** `runtime/api/websocket.py`
**Path:** `ws://<host>/ws`

Initial implementation accepts connections and echoes messages. Planned for:
- Real-time token streaming (alternative to SSE)
- Runtime event notifications (model loading, queue status)
- Future ACRS integration

---

## Future Roadmap

| Feature | Status | Notes |
|---|---|---|
| Function calling execution | 🔜 Planned v1.3 | Schema ready |
| Rate limiting | 🔜 Planned v1.3 | Per-key and global |
| File upload processing | 🔜 Planned v1.4 | With sandboxed storage |
| Vision / multimodal input | 🔜 Planned v2.0 | Requires multimodal engine |
| Prometheus metrics endpoint | 🔜 Planned v1.3 | `/metrics` |
| OpenAPI custom schema | 🔜 Planned v1.3 | APEX-branded Swagger UI |
