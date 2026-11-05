# APEX Troubleshooting Guide

Common issues, diagnostics, and recovery procedures.

For the interactive documentation, visit the [APEX Documentation Website](https://nikhil-kumar-shah.github.io/APEX/troubleshooting.html).

---

## 1. Quick Diagnostics Check

Inspect detected hardware in **Section 1 — Setup & Run APEX** in [`notebook/APEX.ipynb`](../notebook/APEX.ipynb), or issue an HTTP request to `/health`:

```bash
curl http://127.0.0.1:8000/health
```

The output indicates whether the GPU is detected, how much VRAM is allocated, and whether a model is loaded.

---

## 2. Common Issues & Solutions

### A. "CUDA Out of Memory (OOM)"
- **Symptoms**: Runtime fails with `GPUOutOfMemoryError` or `torch.cuda.OutOfMemoryError`.
- **Cause**: The selected model and precision exceed available GPU VRAM.
- **Solutions**:
  1. In Section 1, select a smaller model preset (e.g. `Qwen/Qwen2.5-0.5B` or `Qwen/Qwen2.5-1.5B` instead of `7B`).
  2. Change precision from `float32` to `float16` or `bfloat16`.
  3. In Section 2, click **STOP APEX** to release GPU resources, then re-launch.

### B. "Public Endpoint Unreachable" or Cloudflare Timeout
- **Symptoms**: Stage 10 reports tunnel acquisition timeout.
- **Cause**: Local ISP DNS caching NXDOMAIN or delay in trycloudflare.com subdomain propagation.
- **Solutions**:
  - APEX includes an automatic DNS-over-HTTPS (DoH) resolver querying Cloudflare `1.1.1.1` to bypass ISP propagation delay.
  - Click **START APEX** again to retry tunnel acquisition.
  - If developing locally, set Transport in Advanced Settings to `local`.

### C. "Authentication Required / 401 Unauthorized"
- **Symptoms**: API requests return `HTTP 401: Invalid or missing Bearer authentication token`.
- **Cause**: `enable_auth` is enabled, requiring a valid Bearer token.
- **Solutions**:
  - In Section 1 Connection Panel, click the reveal toggle to copy the active auto-generated API key.
  - Pass header: `Authorization: Bearer <your-key>` in cURL or SDK scripts.
  - To disable authentication, uncheck **Enable Bearer Authentication** in Advanced Settings.

### D. "No module named 'fastapi'" on First Cell in Colab
- **Symptoms**: Running Section 1 yields `ModuleNotFoundError`.
- **Cause**: Fresh Colab instance before automated requirements installation.
- **Solutions**:
  - Re-run Section 1 completely. APEX automatically runs `DependencyInstaller` to install missing packages from `requirements.txt`.

### E. Port 8000 Already in Use
- **Symptoms**: Log outputs `Port 8000 is occupied`.
- **Solutions**:
  - APEX automatically searches up to 10 consecutive ports (`8000–8009`).
  - You can also specify an alternate port (e.g. `8080`) in Advanced Settings.

---

## 3. Reset Procedure

If the runtime enters an inconsistent state:
1. In `notebook/APEX.ipynb`, scroll to **Section 2 — Shutdown APEX** and click **STOP APEX**.
2. In Google Colab menu: **Runtime > Restart session**.
3. Re-execute **Section 1 — Setup & Run APEX**.
