# Server & API Architecture

The server layer transforms the model runtime into a network-accessible server. It supports standard HTTP interfaces, public ngrok tunnels, and request queues.

---

## 🏗️ Components

### 1. FastAPI Application
- **Routing**: Exposes `/health`, `/status`, and standard `/v1/chat/completions` endpoints.
- **SSE Streaming**: Resolves generator outputs and yields JSON chunks for real-time text streaming.

### 2. Request Queue
- **Concurrency Control**: A queue holds incoming requests if active execution thresholds are reached.
- **Backpressure**: Returns HTTP 503 if the request queue limits are exceeded.

### 3. Tunneling Manager
- **ngrok Tunnels**: Dynamically provisions public tunnels.
- **Port Mapping**: Links local FastAPI ports (default `8000`) with public URLs, writing connection credentials back to the workspace configuration.
