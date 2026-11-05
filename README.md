# APEX

**Notebook-first AI model runtime platform with OpenAI-compatible API and Web Chat.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Nikhil-Kumar-Shah/APEX/blob/main/notebook/APEX.ipynb)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-red.svg)](https://apex.nikhilkshah.me/)

---

## What is APEX?

APEX is an open-source platform designed to run modern language models on user-controlled hardware—such as free Google Colab GPUs or local workstations—and expose them as an OpenAI-compatible REST API and interactive web chat application.

It manages model downloading, VRAM allocation, local server execution, and public Cloudflare HTTPS tunneling through an intuitive two-section notebook. External developer tools (including Continue, Cline, Roo Code, Aider, Open WebUI) and official OpenAI SDKs can connect directly without client code alterations.

---

## Key Features

- **Two-Section Notebook:** Clean `Setup & Run APEX` and `Shutdown APEX` interface; zero internal classes or terminal clutter exposed to users.
- **Hugging Face Model Support:** Resolves, downloads, and caches models using repository IDs (e.g. `Qwen/Qwen2.5-1.5B`) or full Hugging Face URLs.
- **OpenAI-Compatible REST API:** Native `/v1/chat/completions` and `/v1/models` endpoints supporting real-time Server-Sent Events (SSE) token streaming.
- **Web Chat Application:** Built-in browser interface at `/chat` with live markdown rendering and document context preview.
- **Document Ingestion:** Extract text context from `.txt`, `.md`, `.pdf`, `.docx`, `.csv`, and `.json` files via `/v1/files`.
- **Zero-Config Public HTTPS:** Automated Cloudflare Quick Tunnel initialization with live public URL acquisition.
- **Hardware-Aware Precision:** Automatically configures `float16`, `bfloat16`, or `float32` based on detected GPU VRAM.
- **Graceful Shutdown:** One-click teardown releasing model weights, server processes, and CUDA VRAM.

---

## Quick Start

Launch the APEX runtime in Google Colab with a single click:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Nikhil-Kumar-Shah/APEX/blob/main/notebook/APEX.ipynb)

1. Open the notebook in Google Colab and ensure a GPU runtime is selected (**Runtime &rarr; Change runtime type &rarr; T4 GPU**).
2. Execute **Section 1 — Setup & Run APEX**. The launcher automatically inspects your hardware and displays detected VRAM.
3. Select a model preset (e.g. `Qwen/Qwen2.5-1.5B`) or paste any Hugging Face URL.
4. Click **START APEX**. The 10-step startup pipeline initializes the environment, loads weights, starts the server, and establishes the tunnel.
5. When the status turns green, click **Open APEX Chat &nearr;** to test the model, or copy your **OpenAI API Base URL** and **API Key**.
6. When finished, scroll to **Section 2 — Shutdown APEX** and click **STOP APEX** to release GPU resources.

---

## Documentation Website

Complete user documentation, API reference, configuration details, and troubleshooting guides are available on the official documentation website:

👉 **[https://apex.nikhilkshah.me/](https://apex.nikhilkshah.me/)**

- [Overview & Architecture](https://apex.nikhilkshah.me/)
- [Getting Started Guide](https://apex.nikhilkshah.me/getting-started.html)
- [Configuration Reference](https://apex.nikhilkshah.me/configuration.html)
- [API & Integration Guide](https://apex.nikhilkshah.me/api.html)
- [Troubleshooting & Diagnostics](https://apex.nikhilkshah.me/troubleshooting.html)
- [Developer & Contributor Guide](https://apex.nikhilkshah.me/development.html)

---

## API Integration Example

Connect the official `openai` Python SDK to your running APEX deployment:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://<your-subdomain>.trycloudflare.com/v1",
    api_key="<your-apex-api-key>"
)

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B",
    messages=[
        {"role": "system", "content": "You are a concise, helpful assistant."},
        {"role": "user", "content": "Hello APEX!"}
    ],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
print()
```

---

## Requirements & Limitations

- **Python:** 3.10 or higher.
- **Compute:** NVIDIA CUDA GPU recommended. Apple Silicon (MPS) and CPU execution supported for compact models.
- **GPU VRAM:** A standard free Google Colab Tesla T4 GPU (15 GB VRAM) supports models up to 7B parameters in `float16`. Models larger than 7B require high-VRAM accelerators (A100/V100).
- **Model Storage:** Model weights are cached locally on fast ephemeral runtime storage (`./cache`). Optional Google Drive mounting is reserved for workspace metadata.

---

## Development & Contributing

To set up a local development environment and run the test suite:

```bash
git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
cd APEX
python -m venv venv
source venv/bin/activate  # Or .\venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# Run the full automated test suite (124 tests)
python -m pytest -v
```

See the [Contributing Guide](CONTRIBUTING.md) and [Development Guide](https://apex.nikhilkshah.me/development.html) for branch workflows and coding standards.

---

## Security & License

- **Security:** Report vulnerabilities according to our [Security Policy](SECURITY.md).
- **License:** APEX is open-source software licensed under the [MIT License](LICENSE).
