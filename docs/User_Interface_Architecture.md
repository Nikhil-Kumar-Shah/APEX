# User Interface Architecture

The user interface provides a graphical, application-like experience inside notebooks. It uses `ipywidgets` to render tab panels, configuration forms, and logs.

---

## 🏗️ Components

### 1. Dashboard Layout
- **Tabs**: Displays resource monitoring, settings edit forms, log outputs, and updates.
- **Headless Fallback**: Automatically bypasses display loops if run outside of interactive notebooks (e.g. during test execution).

### 2. Live Monitors & Controls
- **Resource Monitoring**: Queries RAM, VRAM, and disk free space.
- **Server Controls**: Buttons to start, stop, or restart the background API servers.

### 3. Log & Benchmark Viewer
- **Filter Systems**: Allows users to filter log lines by severity (INFO, WARNING, ERROR) and search query keywords.
- **Benchmarks**: Runs performance tests and displays token speeds and TTFT values.
