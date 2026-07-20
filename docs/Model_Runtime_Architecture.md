# Model Runtime Architecture

**Component:** `runtime/engine/`, `runtime/model/`
**Purpose:** This document describes the design of the inference engine abstraction layer and the model manager — the components responsible for loading, running, and unloading language models within the APEX runtime.

---

## Purpose and Scope

The model runtime layer sits between the API layer and the physical GPU/CPU hardware. Its responsibilities are:

1. **Engine abstraction** — provide a uniform interface for any inference backend, so the API layer never depends on a specific framework.
2. **Model management** — handle model download, cache management, loading, warm-up, and unloading.
3. **VRAM lifecycle** — track memory usage and release resources cleanly.
4. **Metadata provision** — serve model information to the `/v1/models` endpoint.

---

## Architectural Components

```
runtime/model/
├── manager.py       — ModelManager: orchestrates download, load, unload
├── downloader.py    — HuggingFace Hub download with progress tracking
├── cache.py         — Local cache directory management
└── profiles/        — Pre-configured model profiles (Qwen, DeepSeek, etc.)

runtime/engine/
├── base.py          — InferenceEngine abstract base class
├── transformers.py  — TransformersEngine (current primary backend)
├── vllm.py          — VLLMEngine (planned)
├── llamacpp.py      — LlamaCppEngine (planned)
└── __init__.py      — Engine registry {name → class}
```

---

## InferenceEngine Interface

All inference backends must implement the following interface defined in `runtime/engine/base.py`:

```python
class InferenceEngine(ABC):

    @abstractmethod
    def load(self, model_id: str, config: EngineConfig) -> None:
        """Load a model into memory. Must block until ready."""

    @abstractmethod
    def generate(self, prompt: str, params: GenerationParams) -> GenerationResult:
        """Run text generation. Returns complete result (non-streaming)."""

    @abstractmethod
    async def generate_stream(self, prompt: str, params: GenerationParams) -> AsyncGenerator[str, None]:
        """Run streaming text generation. Yields token strings."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate text embeddings. Returns list of float vectors."""

    @abstractmethod
    def unload(self) -> None:
        """Unload the model and release all allocated memory (VRAM/RAM)."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if a model is currently loaded and ready."""

    @abstractmethod
    def get_metadata(self) -> ModelMetadata:
        """Return model metadata (id, context length, capabilities)."""
```

**Design invariant:** The API layer (`runtime/api/`) imports only from `runtime/model/manager.py`. It never imports from `runtime/engine/` directly.

---

## Engine Registry

Engines are registered by string key in `runtime/engine/__init__.py`:

```python
ENGINES = {
    "transformers": TransformersEngine,
    "vllm": VLLMEngine,           # planned
    "llamacpp": LlamaCppEngine,   # planned
}
```

The active engine is selected by the config key `model.engine` in `apex.config.json`.

---

## TransformersEngine (Current Backend)

**Status:** ✅ Implemented

**Dependencies:** `torch`, `transformers` (Hugging Face)

**Lifecycle:**

```
load()
  │
  ├─ Resolve model path (local cache or HF Hub)
  ├─ Load tokenizer (AutoTokenizer.from_pretrained)
  ├─ Load model (AutoModelForCausalLM.from_pretrained)
  │   ├─ device_map = "auto" (multi-GPU support)
  │   ├─ torch_dtype = bf16 / fp16 / fp32 (from config)
  │   └─ trust_remote_code = True (for custom architectures)
  ├─ Move model to target device
  └─ Set model.eval()

generate()
  │
  ├─ Tokenize input (tokenizer.apply_chat_template or manual)
  ├─ model.generate() with sampling parameters
  ├─ Decode output tokens
  └─ Return GenerationResult (text, token counts)

generate_stream()
  │
  ├─ TextIteratorStreamer initialised
  ├─ model.generate() run in background thread
  └─ Yield tokens as they arrive → SSE via streaming.py

unload()
  ├─ del model, del tokenizer
  ├─ torch.cuda.empty_cache()
  └─ gc.collect()
```

**Supported configuration:**

| Config key | Values | Description |
|---|---|---|
| `model.precision` | `bf16`, `fp16`, `fp32` | Torch dtype for loading |
| `model.device` | `cuda`, `cpu`, `auto` | Target device |
| `model.trust_remote_code` | `true` / `false` | Allow custom model code |
| `model.max_new_tokens` | integer | Default generation limit |

---

## Model Manager

**Module:** `runtime/model/manager.py`

The `ModelManager` is the single point of contact for all model operations. It:

- Selects and instantiates the correct engine based on config.
- Delegates download and cache checks to `downloader.py` and `cache.py`.
- Maintains the loaded model state and metadata.
- Provides model information for `/v1/models`.

```python
# Simplified interface
class ModelManager:
    def load_model(self) -> None: ...
    def unload_model(self) -> None: ...
    def generate(self, prompt, params) -> GenerationResult: ...
    async def generate_stream(self, prompt, params) -> AsyncGenerator[str, None]: ...
    def embed(self, texts) -> list[list[float]]: ...
    def list_models(self) -> list[ModelMetadata]: ...
    def get_current_model(self) -> ModelMetadata | None: ...
```

---

## Model Download Flow

```
ModelManager.load_model()
      │
      ▼
downloader.is_cached(model_id)
      │
  ┌───┴────────────────────────┐
  │ YES                        │ NO
  ▼                            ▼
load from local cache    huggingface_hub.snapshot_download()
                               │
                               ▼
                         verify file integrity
                               │
                               ▼
                         store in local cache
```

Cache directory: `~/.cache/huggingface/hub/` (default HF cache) or the path configured in `model.cache_dir`.

---

## Pre-configured Model Profiles

Located in `runtime/model/profiles/`. Each profile is a JSON file specifying defaults:

```json
{
  "id": "Qwen/Qwen2.5-7B-Instruct",
  "engine": "transformers",
  "precision": "bf16",
  "device": "cuda",
  "context_length": 32768,
  "capabilities": ["chat", "completion", "code"],
  "chat_template": "qwen"
}
```

Available profiles:

| Profile | Model | Parameters | Capabilities |
|---|---|---|---|
| `qwen-7b` | `Qwen/Qwen2.5-7B-Instruct` | 7B | chat, code, instruction |
| `qwen-coder-7b` | `Qwen/Qwen2.5-Coder-7B-Instruct` | 7B | code, completion |
| `deepseek-coder-6.7b` | `deepseek-ai/DeepSeek-Coder-6.7B-Instruct` | 6.7B | code |
| `gemma-9b` | `google/gemma-2-9b-it` | 9B | chat, instruction |
| `glm-9b` | `THUDM/glm-4-9b-chat` | 9B | chat, multilingual |

---

## Extensibility

To add a new inference backend:

1. Create `runtime/engine/my_engine.py` implementing `InferenceEngine`.
2. Register in `runtime/engine/__init__.py`: `ENGINES["my_engine"] = MyEngine`.
3. Add `"my_engine"` as a valid value for `model.engine` in the config schema.
4. Document the new backend and its configuration in this file.
5. Write tests in `tests/test_engine.py`.

The API layer requires no changes when a new engine is added.

---

## Future Roadmap

| Backend | Status | Notes |
|---|---|---|
| Hugging Face Transformers | ✅ Implemented | Primary backend |
| vLLM (PagedAttention) | 🔜 Planned v1.3 | High-throughput serving |
| llama.cpp (GGUF) | 🔜 Planned v1.3 | CPU/quantised inference |
| ONNX Runtime | 🔜 Planned v2.0 | Edge deployment |
| ACRS (Custom Runtime) | 🔜 Planned v2.0 | Internal APEX engine |
