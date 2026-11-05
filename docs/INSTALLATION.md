# Installation Guide

APEX can be deployed in a Google Colab notebook (recommended for free GPUs) or on a local machine.

---

## Method 1: Google Colab (Recommended)

The fastest and easiest way to deploy APEX is with the ready-to-run notebook:

1. Click **[Open APEX in Google Colab](https://colab.research.google.com/github/Nikhil-Kumar-Shah/APEX/blob/main/notebook/APEX.ipynb)**.
2. In Google Colab, verify GPU acceleration: **Runtime > Change runtime type > T4 GPU**.
3. Run **Section 1 — Setup & Run APEX**, select a model, and click **START APEX**.

For the full step-by-step walkthrough, see the [Getting Started Guide](https://nikhil-kumar-shah.github.io/APEX/getting-started.html).

---

## Method 2: Local Installation

**Prerequisites:**
- Python 3.10+
- Git
- NVIDIA GPU with CUDA drivers (optional, but highly recommended for performance)

**Steps:**

1. **Clone the repository**
```bash
git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
cd APEX
```

2. **Create a virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install APEX in editable mode**
```bash
pip install -e ".[dev,ml]"
```

4. **Verify the installation**
```bash
pytest tests/ -v
```

5. **Start the API server**
```bash
python -m runtime.api.server
```

---

## Troubleshooting

### "CUDA Out of Memory"
Edit `configs/apex.config.json` and change the model to a smaller variant (e.g., 7B instead of 9B), or ensure no other processes are using the GPU.

### "Authentication Error" from Client
If `enable_auth` is true in your config, ensure your client is sending the correct Bearer token.

### Colab Drive Mount Fails
Ensure you grant Google Drive access when prompted by the Colab UI popup during the bootstrap sequence.
