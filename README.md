# APEX

Adaptive Platform for Unified AI Platform Configuration, Orchestration and Workspace Management

> **Configure once. Run any supported AI. Manage everything from one unified workspace.**

---

## 🌌 Overview

**APEX** is a modular, production-quality runtime environment and workspace orchestration manager. It acts as a unified translation layer that allows developers to run, monitor, and query open-source LLMs (using Transformers, vLLM, or llama.cpp backends) from a single API interface or visual dashboard. 

APEX operates under a **GitHub-first deployment architecture**: the core runtime lives entirely within a version-controlled git repository, while lightweight notebooks or local commands bootstrap the installation, resolve dependencies, and launch services.

---

## 🛠️ Key Features

- **Unified Runtime**: Decouples underlying inference execution from application APIs.
- **Multi-Model Support**: Pre-configured profiles for Qwen, DeepSeek, Gemma, and GLM.
- **Google Colab & Local Environments**: Run identical pipelines in ephemeral cloud notebooks and local hardware.
- **Workspace Persistence**: Tracks conversation histories, symbols index directories, and projects state across notebook reconnects.
- **OpenAI-Compatible API**: Seamless drop-in replacement for downstream tools (Cline, Continue, Roo Code).
- **Interactive Dashboard**: Graphical control panels built with `ipywidgets` for configurations, log outputs, and benchmarks.
- **Diagnostics & Benchmarks**: Real-time VRAM allocation metrics, generation speeds, and latency tracking.

---

## 🏗️ Architecture Overview

APEX separates user presentation interfaces, connection managers, inference adapters, and physical storage drivers into decoupled packages:

```text
       [ User Dashboard / API Clients ]
                      │
                      ▼
            [ Runtime Controller ]
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
  [Server Manager] [Model Manager] [Workspace Manager]
        │             │             │
        ▼             ▼             ▼
   (FastAPI)     (Inference)    (SQLite/JSON)
```

---

## 🚀 Installation & Getting Started

### Google Colab Bootstrap

Run the following cell to clone the repository, install Python requirements, validate configuration integrity, and mount Google Drive folders automatically:

```python
!git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
%cd APEX
from bootstrap.installer import InstallationWizard
from bootstrap.launcher import RuntimeLauncher

# Run installation setup
wizard = InstallationWizard(workspace_parent_dir=Path.cwd(), repo_url="https://github.com/Nikhil-Kumar-Shah/APEX.git")
project_path = wizard.run(interactive=True)

# Launch system
if project_path:
    launcher = RuntimeLauncher(project_path)
    launcher.launch()
```

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
   cd APEX
   ```
2. **Install editable package**:
   ```bash
   pip install -e .[dev,ml]
   ```
3. **Execute unit tests**:
   ```bash
   pytest tests/
   ```

---

## ⚙️ Configuration Properties

All parameters reside inside `configs/apex.config.json`. The schema requires:


| Field | Type | Description |
| :--- | :--- | :--- |
| `project_id` | `string` | Unique project slug (e.g., `default-workspace`). |
| `project_name` | `string` | Display name of the workspace. |
| `runtime_version` | `string` | Installed package version target. |
| `config_version` | `string` | Internal configuration schema migration identifier. |

---

## 🧬 Supported Inference Engines

- **Transformers**: Hugging Face native inference loader supporting high-precision configurations.
- **vLLM**: PagedAttention memory-optimized throughput backend for high-concurrency needs.
- **llama.cpp**: Efficient CPU/GPU quantized inference via GGUF files.

---

## 📡 API Overview

APEX exposes standard endpoints for integration with LLM coding tools:

- `GET /health`: Fast system status and diagnostics summaries.
- `GET /status`: Live RAM, VRAM, disk free space, and cache statistics.
- `GET /v1/models`: Retrieve list of active/cached model profiles.
- `POST /v1/chat/completions`: OpenAI-compatible text generation (supports SSE streaming).

---

## 📖 Documentation Index

For detailed guidelines, inspect the documentation folder:
- [Developer Guide](file:///d:/APEX/docs/DEVELOPER_GUIDE.md)
- [Model Runtime Architecture](file:///d:/APEX/docs/Model_Runtime_Architecture.md)
- [Server API Architecture](file:///d:/APEX/docs/Server_API_Architecture.md)
- [Memory Workspace Architecture](file:///d:/APEX/docs/Memory_Workspace_Architecture.md)
- [User Interface Architecture](file:///d:/APEX/docs/User_Interface_Architecture.md)
- [Release Process Guide](file:///d:/APEX/docs/RELEASE_PROCESS.md)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
