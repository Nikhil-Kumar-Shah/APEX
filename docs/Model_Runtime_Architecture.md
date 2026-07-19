# Model Runtime Architecture

The model runtime manages model caching, profile parsing, and inference engines configuration. It provides a standardized framework that isolates the complexities of various ML inference backends from user-facing services.

---

## 🏗️ Components

```text
    ┌───────────────────────┐
    │     Model Manager     │
    └───────────┬───────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
 ┌─────────────┐ ┌─────────────┐
 │ Downloader  │ │    Cache    │
 └─────────────┘ └─────────────┘
```

### 1. Model Profiles
Configurations for models (e.g. Qwen, DeepSeek, Gemma, GLM) are defined as profiles specifying:
- **Repo ID**: Target Hugging Face Hub repository.
- **Quantization**: Formats (AWQ, GPTQ, GGUF) and precision limits.
- **Engine Capability**: Mappings between backend executors and model weights.

### 2. Cache & Downloader
- **HF Hub Downloader**: Performs secure snapshot file downloads with file locks and checksum validation.
- **Model Cache**: Manages disk files, verifies checksum hashes, and lists downloaded structures.

### 3. Inference Engines
The runtime implements an adapter pattern exposing a unified interface (`BaseEngineAdapter`):
- **Transformers Engine**: Standard PyTorch execution.
- **vLLM Engine**: High-throughput inference leveraging PagedAttention.
- **llama.cpp Engine**: Quantized execution targeting low resource systems.
