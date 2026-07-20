# APEX API Reference

**Base URL:** `http://localhost:8000/v1` (or your tunnel URL)

APEX implements an OpenAI-compatible REST API. Any client that supports configuring a custom `base_url` can connect to APEX as if it were OpenAI.

---

## Table of Contents

- [Authentication](#authentication)
- [Streaming](#streaming)
- [Core Endpoints](#core-endpoints)
  - [GET /health](#get-health)
  - [GET /runtime](#get-runtime)
  - [GET /version](#get-version)
- [OpenAI Endpoints](#openai-endpoints)
  - [GET /v1/models](#get-v1models)
  - [GET /v1/models/{id}](#get-v1modelsid)
  - [POST /v1/chat/completions](#post-v1chatcompletions)
  - [POST /v1/completions](#post-v1completions)
  - [POST /v1/embeddings](#post-v1embeddings)
- [Planned Endpoints](#planned-endpoints)
- [Error Codes](#error-codes)

---

## Authentication

Authentication is configurable via `apex.config.json` (`api.enable_auth`).

If enabled, all endpoints require a Bearer token:

```http
Authorization: Bearer <your-api-key>
```

If disabled, the `Authorization` header is ignored.

---

## Streaming

APEX supports Server-Sent Events (SSE) streaming for text generation. 

To enable streaming, set `"stream": true` in the request body.

The response will be a stream of events:

```http
data: {"id": "chatcmpl-123", "object": "chat.completion.chunk", "model": "qwen-7b", "choices": [{"delta": {"content": "Hello"}}]}

data: {"id": "chatcmpl-123", "object": "chat.completion.chunk", "model": "qwen-7b", "choices": [{"delta": {"content": " world"}}]}

data: [DONE]
```

---

## Core Endpoints

### GET `/health`
Returns the current health status of the APEX runtime.

**Response (200 OK):**
```json
{
  "status": "ok",
  "uptime": 3600.5,
  "gpu": true,
  "memory": "ok",
  "model": "loaded",
  "queue": "active",
  "workers": 1
}
```

### GET `/runtime`
Returns detailed information about the active runtime configuration and VRAM usage.

**Response (200 OK):**
```json
{
  "loaded_model": "Qwen/Qwen2.5-7B-Instruct",
  "vram": "14.2GB",
  "cpu": "12%",
  "ram": "8.5GB",
  "tokenizer": "fast",
  "engine": "transformers",
  "device": "cuda:0",
  "precision": "bf16",
  "queue": 0,
  "transport": "http",
  "api_version": "v1"
}
```

### GET `/version`
Returns the APEX system version information.

**Response (200 OK):**
```json
{
  "runtime_version": "1.2.0",
  "api_version": "v1",
  "build": "stable",
  "commit": "a1b2c3d4",
  "compatibility": ["openai"]
}
```

---

## OpenAI Endpoints

### GET `/v1/models`
Lists all currently loaded and cached models available for inference.

**Response (200 OK):**
```json
{
  "object": "list",
  "data": [
    {
      "id": "apex-runtime-model",
      "object": "model",
      "created": 1721471000,
      "owned_by": "apex"
    }
  ]
}
```

### GET `/v1/models/{id}`
Retrieve details about a specific model.

**Path Parameters:**
- `id` (string): The model identifier.

**Response (200 OK):**
```json
{
  "id": "apex-runtime-model",
  "object": "model",
  "created": 1721471000,
  "owned_by": "apex"
}
```

### POST `/v1/chat/completions`
Creates a model response for the given chat conversation.

**Request Body:**
```json
{
  "model": "apex-runtime-model",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "stream": false
}
```

**Response (200 OK):**
```json
{
  "id": "chatcmpl-1234567890ab",
  "object": "chat.completion",
  "created": 1721471000,
  "model": "apex-runtime-model",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 9,
    "total_tokens": 24
  }
}
```

### POST `/v1/completions`
Creates a completion for the provided prompt (legacy).

**Request Body:**
```json
{
  "model": "apex-runtime-model",
  "prompt": "Once upon a time",
  "max_tokens": 50
}
```

### POST `/v1/embeddings`
Creates an embedding vector representing the input text.

**Request Body:**
```json
{
  "model": "apex-runtime-model",
  "input": "The food was delicious and the waiter..."
}
```

---

## Planned Endpoints (501 Not Implemented)

The following endpoints are defined in the router but currently return `501 Not Implemented`. They will be fully implemented in future releases.

- `POST /v1/images/generations`
- `POST /v1/images/edits`
- `POST /v1/images/variations`
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/translations`
- `POST /v1/audio/speech`
- `POST /v1/files`
- `GET /v1/files`
- `DELETE /v1/files/{id}`
- `POST /v1/vision`
- `POST /v1/images/analyze`
- `POST /v1/responses`

---

## Error Codes

APEX errors strictly follow the OpenAI error format. You will never see a raw Python traceback in the API response.

```json
{
  "error": {
    "message": "Human-readable error description.",
    "type": "invalid_request_error",
    "code": "model_not_found",
    "details": {
      "resolution": "Actionable advice on how to fix the error."
    }
  }
}
```

| HTTP Status | Type | Common Codes | Description |
|---|---|---|---|
| `400` | `invalid_request_error` | `invalid_parameter` | Bad request body or missing fields |
| `401` | `authentication_error` | `invalid_api_key` | Missing or incorrect Bearer token |
| `404` | `invalid_request_error` | `model_not_found` | Requested model ID is not loaded |
| `429` | `rate_limit_error` | `rate_limit_exceeded` | Too many requests in queue |
| `500` | `internal_server_error` | `unexpected_error` | Internal runtime exception |
| `501` | `not_implemented_error` | `endpoint_not_implemented` | Future capability not yet built |
| `503` | `runtime_error` | `model_not_loaded` | Server running but inference engine off |
