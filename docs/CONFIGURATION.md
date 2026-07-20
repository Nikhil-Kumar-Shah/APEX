# Configuration Guide

APEX relies on a single configuration file for all runtime behavior: `configs/apex.config.json`.

---

## Default Configuration File

```json
{
  "project_id": "default-workspace",
  "project_name": "APEX Default Workspace",
  "runtime_version": "1.2.0",
  "config_version": "1.0",
  "model": {
    "id": "Qwen/Qwen2.5-7B-Instruct",
    "engine": "transformers",
    "precision": "bf16",
    "device": "cuda",
    "trust_remote_code": true,
    "max_new_tokens": 4096
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "enable_auth": false,
    "api_key": "",
    "enable_request_logs": true,
    "cors_origins": ["*"]
  },
  "workspace": {
    "persistence": "google_drive",
    "drive_path": "/content/drive/MyDrive/APEX"
  }
}
```

---

## Core Properties

| Field | Type | Description |
|---|---|---|
| `project_id` | `string` | Unique slug for the workspace. Used as folder name. |
| `project_name` | `string` | Human-readable name displayed in the UI. |
| `runtime_version` | `string` | Target APEX version to load. |
| `config_version` | `string` | Internal schema version for automatic migrations. |

## Model Configuration (`model`)

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Hugging Face model ID (e.g., `Qwen/Qwen2.5-7B-Instruct`). |
| `engine` | `string` | Inference backend: `transformers` (vLLM/llamacpp planned). |
| `precision` | `string` | Float precision: `bf16`, `fp16`, `fp32`. |
| `device` | `string` | Target hardware: `cuda`, `cpu`, `auto`. |
| `trust_remote_code` | `boolean` | Allow custom model architectures from HF Hub. |
| `max_new_tokens` | `integer` | Default maximum generation length. |

## API Configuration (`api`)

| Field | Type | Description |
|---|---|---|
| `host` | `string` | Interface to bind (default `0.0.0.0`). |
| `port` | `integer` | Server port (default `8000`). |
| `enable_auth` | `boolean` | Require Bearer token authentication. |
| `api_key` | `string` | The API key expected (if `enable_auth` is true). |
| `enable_request_logs` | `boolean` | Log every HTTP request to the console. |
| `cors_origins` | `array` | Allowed CORS domains. |

## Workspace Configuration (`workspace`)

| Field | Type | Description |
|---|---|---|
| `persistence` | `string` | Storage backend: `google_drive` or `local`. |
| `drive_path` | `string` | Root folder path when mounted in Colab. |

---

## Environment Variables

APEX also respects standard environment variables, which override `apex.config.json` values:

- `APEX_API_KEY`: Overrides `api.api_key`
- `APEX_MODEL_ID`: Overrides `model.id`
- `APEX_PORT`: Overrides `api.port`
- `HF_TOKEN`: Used automatically for downloading gated models from Hugging Face.

## Schema Validation

On startup, APEX validates `apex.config.json`. If fields are missing or invalid, it will attempt a migration or abort startup with a clear error message in the console.
