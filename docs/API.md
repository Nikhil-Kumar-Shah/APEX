# APEX API Reference & OpenAI Compatibility Guide

APEX exposes an OpenAI-compatible REST API. Developer extensions and tools—including **Continue**, **Cline**, **Roo Code**, **Aider**, **Open WebUI**, and standard **OpenAI SDKs**—can interact with APEX without client code modifications.

---

## 1. Quick Integration

### Python (OpenAI SDK v1.0+)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://<your-subdomain>.trycloudflare.com/v1",
    api_key="your-api-key" # or "not-needed" if authentication is disabled
)

# Streaming Chat Completion
response = client.chat.completions.create(
    model="Qwen/Qwen2.5-0.5B",
    messages=[
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a Python function to compute Fibonacci numbers."}
    ],
    temperature=0.7,
    max_tokens=512,
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

### cURL

```bash
curl -X POST https://<your-subdomain>.trycloudflare.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "Qwen/Qwen2.5-0.5B",
    "messages": [{"role": "user", "content": "Hello APEX!"}],
    "temperature": 0.7,
    "max_tokens": 128
  }'
```

---

## 2. Supported Endpoints

### Chat & Completions
| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/v1/chat/completions` | `POST` | OpenAI-compatible chat completion. Supports `stream: true` (SSE) and non-streaming. |
| `/v1/completions` | `POST` | Classic raw prompt text completion. |

### Models & Discovery
| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/v1/models` | `GET` | Lists loaded and active models. |
| `/v1/models/{model_id}` | `GET` | Retrieves details for a specific model. |
| `/health` | `GET` | Dynamic runtime health status, GPU allocation, and queue depth. |
| `/runtime` | `GET` | Hardware telemetry (VRAM, CPU, RAM, precision, device). |
| `/version` | `GET` | APEX version and platform metadata. |

### Document & File Ingestion
| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/v1/files` | `POST` | Upload and process a document (`multipart/form-data`). |
| `/v1/files` | `GET` | List all processed files in the active workspace. |
| `/v1/files/{file_id}` | `GET` | Retrieve file metadata, text preview, and extracted context. |
| `/v1/files/{file_id}` | `DELETE`| Remove file from disk and active registry. |

### Conversation Management
| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/v1/conversations` | `GET` | List all stored conversation sessions. |
| `/v1/conversations` | `POST` | Create a new conversation session. |
| `/v1/conversations/{id}` | `GET` | Retrieve full message history of a session. |
| `/v1/conversations/{id}` | `DELETE`| Delete a conversation history session. |

---

## 3. Parameter Support Matrix

| Parameter | Supported in APEX | Notes |
| :--- | :---: | :--- |
| `model` | **Yes** | Uses the model currently loaded in the APEX runtime. |
| `messages` | **Yes** | Standard role-content array (`system`, `user`, `assistant`). |
| `stream` | **Yes** | Real-time Server-Sent Events (SSE) token generator. |
| `temperature` | **Yes** | Float between 0.0 and 2.0 (0.0 enables greedy decoding). |
| `max_tokens` / `max_new_tokens` | **Yes** | Upper limit on generated tokens. Defaults to 512. |
| `top_p` | **Yes** | Nucleus sampling probability threshold. |
| `conversation_id` | **Yes** | APEX extension: associates request with persistent session. |
| `tools` / `tool_choice` | *Planned* | Evaluated in upcoming runtime releases. |
| `n` (multiple completions) | *No* | Returns single completion (`n=1`). |

---

## 4. Error Responses

APEX adheres to OpenAI error standards:

```json
{
  "error": {
    "message": "No model is currently loaded in APEX runtime.",
    "type": "invalid_request_error",
    "param": null,
    "code": "503"
  }
}
```

