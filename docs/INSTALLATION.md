# Installation Guide

APEX can be deployed in a Google Colab notebook (recommended for free GPUs) or on a local machine.

---

## Method 1: Google Colab (Recommended)

1. Open [Google Colab](https://colab.research.google.com).
2. Create a New Notebook.
3. In the menu, go to **Runtime > Change runtime type** and select a **T4 GPU** (or better).
4. Paste the following into the first cell and run it:

```python
# Clone the repository
!git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
%cd APEX

# Run the interactive setup wizard
from pathlib import Path
from bootstrap.installer import InstallationWizard
from bootstrap.launcher import RuntimeLauncher

wizard = InstallationWizard(
    workspace_parent_dir=Path.cwd(),
    repo_url="https://github.com/Nikhil-Kumar-Shah/APEX.git"
)
project_path = wizard.run(interactive=True)

# Launch the runtime
if project_path:
    launcher = RuntimeLauncher(project_path)
    launcher.launch()
```

The wizard will mount your Google Drive automatically to ensure your workspace survives session resets.

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
