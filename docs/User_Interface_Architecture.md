# User Interface Architecture

**Component:** `runtime/ui/`
**Purpose:** This document describes the design of the APEX notebook control panel — the lightweight `ipywidgets`-based dashboard that renders at the bottom of the Jupyter/Colab cell output and provides quick runtime controls and status monitoring.

---

## Purpose and Scope

APEX's primary output surface is the **notebook console** — the standard stdout/stderr cell output. This is the authoritative runtime log. Every event, error, and metric is printed here in structured, colour-coded format.

The `ipywidgets` dashboard exists as a **complement**, not a replacement. It provides:

- Quick controls (start/stop server, load/unload model) without requiring the user to rerun cells.
- A live status summary (GPU, VRAM, model state, queue length) at a glance.
- Non-destructive interaction — the dashboard never interferes with the log output stream.

---

## Design Principles

| Principle | Implementation |
|---|---|
| **Non-intrusive** | Dashboard anchored at the bottom, logs remain primary |
| **Lightweight** | Pure `ipywidgets` — no heavy JS frameworks |
| **Tab-based** | Related controls grouped into logical tabs |
| **Status-mirroring** | Dashboard always reflects actual runtime state |
| **Graceful degradation** | If `ipywidgets` is unavailable, APEX runs headlessly |

---

## Module Structure

```
runtime/ui/
├── dashboard.py      — Main Dashboard class, tab layout, render logic
├── tabs/
│   ├── runtime_tab.py    — Runtime status, server controls
│   ├── models_tab.py     — Model load/unload, profile selector
│   ├── workspace_tab.py  — Active workspace, conversation count
│   ├── logs_tab.py       — Log search and filter view
│   └── config_tab.py     — Live configuration display
├── widgets.py         — Reusable widget components (StatusBadge, MetricBar, etc.)
└── updater.py         — Periodic state polling and widget refresh
```

---

## Tab Layout

```
┌──────────────────────────────────────────────────────────────┐
│  ⚙ Runtime  │  🤖 Models  │  📁 Workspace  │  📋 Logs  │  🔧 Config  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Tab content area]                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### ⚙ Runtime Tab

Displays live system state and server controls.

| Widget | Description |
|---|---|
| Status badge | `RUNNING` / `STOPPED` / `LOADING` with colour coding |
| Public URL | Current tunnel URL (clickable) |
| Uptime | Time since server start |
| GPU | GPU model name |
| VRAM | Used / Total (progress bar) |
| RAM | Used / Total (progress bar) |
| Queue | Active requests / queue depth |
| [Start Server] | Launches API server + tunnel |
| [Stop Server] | Gracefully terminates server |
| [Restart Server] | Stop + Start sequence |

### 🤖 Models Tab

| Widget | Description |
|---|---|
| Loaded model | Current model ID or "None" |
| Model profile dropdown | Select from pre-configured profiles |
| [Load Model] | Download if needed and load into VRAM |
| [Unload Model] | Release VRAM |
| VRAM after load | Predicted VRAM usage for selected profile |
| Precision selector | `bf16` / `fp16` / `fp32` |

### 📁 Workspace Tab

| Widget | Description |
|---|---|
| Active workspace | Current project ID |
| Project name | Display name |
| Conversation count | Total sessions logged |
| Last active | Timestamp |
| [New Workspace] | Create a new project context |
| [Switch Workspace] | Load a different project |
| Drive sync status | Last sync timestamp |

### 📋 Logs Tab

Provides a searchable view of the most recent log lines without scrolling the full console.

| Widget | Description |
|---|---|
| Log level filter | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| Search box | Keyword filter |
| Log output area | Scrollable text area, last 200 lines |
| [Refresh] | Reload from in-memory log buffer |

### 🔧 Config Tab

Displays the active `apex.config.json` contents in a formatted, read-only view. Provides a [Reload Config] button to reparse the file without restarting the runtime.

---

## Widget Rendering

The dashboard is rendered by calling `Dashboard.display()` from the notebook cell:

```python
from runtime.ui.dashboard import Dashboard
from runtime.orchestrator import get_runtime_state

dashboard = Dashboard(state=get_runtime_state())
dashboard.display()
```

This renders an `ipywidgets.Tab` widget anchored at the bottom of the cell output using `IPython.display.display()`.

---

## State Polling

**Module:** `runtime/ui/updater.py`

The `Updater` class uses `ipywidgets.widget_events` and a background thread to poll the runtime state every 5 seconds and push updates to the displayed widgets. This keeps GPU, VRAM, queue, and status indicators live without requiring user interaction.

```python
class Updater:
    interval_seconds: int = 5

    def start(self) -> None: ...   # starts background polling thread
    def stop(self) -> None: ...    # stops polling
    def tick(self) -> None: ...    # one poll cycle: read state, update widgets
```

---

## Graceful Degradation

If `ipywidgets` is not installed or the notebook environment does not support it, `Dashboard.display()` catches the `ImportError` and prints a plain-text status summary to stdout instead. The runtime continues normally.

---

## Future Roadmap

| Feature | Status | Notes |
|---|---|---|
| Basic ipywidgets dashboard | ✅ Implemented | Tab-based control panel |
| Periodic state polling | ✅ Implemented | 5-second update interval |
| Benchmark panel | 🔜 Planned v1.3 | Tokens/sec, latency histogram |
| Token streaming preview | 🔜 Planned v1.3 | Live completions in the dashboard |
| Web UI (Open WebUI integration) | 🔜 Planned v2.0 | Browser-based interface |
| Mobile-responsive dashboard | 🔜 Planned v2.0 | Works on phone browsers |
