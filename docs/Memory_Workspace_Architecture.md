# Memory & Workspace Architecture

**Component:** `runtime/memory/`, `runtime/drive/`
**Purpose:** This document describes the workspace isolation model, conversation history persistence, Google Drive integration, the AST-based codebase indexer, and how APEX maintains state across session boundaries.

---

## Purpose and Scope

APEX is designed to run in ephemeral environments (Google Colab sessions that reset every few hours). The memory and workspace subsystem solves this by:

1. **Persisting all meaningful state** to Google Drive (or a local directory) so it survives Colab resets.
2. **Isolating workspace contexts** so multiple projects can share the same APEX instance without interfering.
3. **Recording conversation history** in a structured format that can be reloaded and indexed.
4. **Indexing codebases** using AST analysis for future code-aware prompting.

---

## Module Structure

```
runtime/memory/
├── workspace.py      — WorkspaceManager: create, load, switch workspaces
├── history.py        — ConversationLogger: record and retrieve messages
├── indexer.py        — SymbolIndexer: AST-based codebase symbol extraction
└── models.py         — Pydantic models for workspace state, conversation entries

runtime/drive/
├── mount.py          — Google Drive mounting for Colab environments
├── sync.py           — File synchronisation between VM and Drive
└── resolver.py       — Path resolution (Drive vs. local fallback)
```

---

## Workspace Model

A **workspace** in APEX is a named, isolated context associated with a project. It contains:

```
workspaces/
└── <project_id>/
    ├── workspace.json       — Workspace metadata and configuration
    ├── history/
    │   └── conversations/
    │       └── <session_id>.json   — Conversation history
    └── index/
        └── symbols.json     — AST symbol index for the project codebase
```

`workspace.json` schema:

```json
{
  "project_id": "my-project",
  "project_name": "My Project",
  "created_at": "2026-07-20T14:00:00Z",
  "last_active": "2026-07-20T19:00:00Z",
  "config_version": "1.0",
  "model_id": "Qwen/Qwen2.5-7B-Instruct",
  "conversation_count": 12,
  "index_updated_at": "2026-07-20T18:30:00Z"
}
```

---

## WorkspaceManager

**Module:** `runtime/memory/workspace.py`

Responsibilities:
- Create new workspace directories with the correct structure.
- Load existing workspace state from disk.
- Switch the active workspace context.
- Return workspace metadata to the API and UI.

```python
class WorkspaceManager:
    def create(self, project_id: str, project_name: str) -> Workspace: ...
    def load(self, project_id: str) -> Workspace: ...
    def list_workspaces(self) -> list[WorkspaceSummary]: ...
    def get_active(self) -> Workspace | None: ...
    def set_active(self, project_id: str) -> None: ...
    def delete(self, project_id: str) -> None: ...
```

---

## Conversation History

**Module:** `runtime/memory/history.py`

Conversation history is stored in JSON files — one file per conversation session:

```json
{
  "session_id": "sess_20260720_190000",
  "workspace_id": "my-project",
  "model_id": "Qwen/Qwen2.5-7B-Instruct",
  "started_at": "2026-07-20T19:00:00Z",
  "messages": [
    {
      "id": "msg_001",
      "timestamp": "2026-07-20T19:00:05Z",
      "role": "user",
      "content": "Explain the workspace architecture.",
      "tokens": 8
    },
    {
      "id": "msg_002",
      "timestamp": "2026-07-20T19:00:12Z",
      "role": "assistant",
      "content": "The workspace architecture in APEX...",
      "tokens": 142,
      "latency_ms": 2300
    }
  ],
  "total_tokens": 150
}
```

**ConversationLogger interface:**

```python
class ConversationLogger:
    def start_session(self, workspace_id: str, model_id: str) -> str: ...  # returns session_id
    def log_message(self, session_id: str, role: str, content: str, tokens: int = 0) -> None: ...
    def get_session(self, session_id: str) -> ConversationSession: ...
    def list_sessions(self, workspace_id: str) -> list[SessionSummary]: ...
```

---

## AST Symbol Indexer

**Module:** `runtime/memory/indexer.py`

The symbol indexer performs static analysis of Python codebases using Python's built-in `ast` module. It extracts:

- Module names and docstrings
- Class definitions, base classes, docstrings
- Method and function signatures, parameters, return types
- Module-level constants and variables

Output is stored in `workspaces/<project_id>/index/symbols.json`:

```json
{
  "indexed_at": "2026-07-20T18:30:00Z",
  "root_path": "/content/APEX",
  "files": 47,
  "symbols": {
    "runtime.api.chat": {
      "type": "module",
      "functions": ["chat_completions"],
      "classes": []
    },
    "runtime.model.manager.ModelManager": {
      "type": "class",
      "methods": ["load_model", "unload_model", "generate", "embed", "list_models"],
      "docstring": "Manages model lifecycle and delegates to inference engines."
    }
  }
}
```

This index is the foundation for future code-aware context injection.

---

## Google Drive Integration

**Module:** `runtime/drive/`

Google Drive persistence is used in Colab environments where the VM state is ephemeral.

### Mount Flow

```
mount.py: mount_drive()
      │
      ├─ Check: is this a Colab environment?
      │
      ├─ YES → google.colab.drive.mount('/content/drive')
      │         └─ Wait for mount confirmation
      │
      └─ NO  → Use local filesystem path from config
               (workspace.persistence = "local")
```

### Sync Strategy

On each state change, the workspace directory is synced to Drive:

```
VM path:    /content/APEX/workspaces/<project_id>/
Drive path: /content/drive/MyDrive/APEX/workspaces/<project_id>/
```

Sync is **incremental** — only changed files are copied. Full sync happens on graceful shutdown.

### Path Resolver

`runtime/drive/resolver.py` provides a single `resolve_path()` function that returns the correct path whether Drive is mounted or not:

```python
def resolve_path(relative: str, config: WorkspaceConfig) -> Path:
    if config.persistence == "google_drive" and is_drive_mounted():
        return DRIVE_BASE / relative
    return LOCAL_BASE / relative
```

---

## State Persistence During Session Reset

Colab session resets clear `/content/` but leave Google Drive intact. The bootstrap sequence handles this:

```
New Colab session
      │
      ▼
bootstrap/installer.py
      │
      ├─ git pull (update code from GitHub)
      ├─ pip install (restore Python packages)
      ├─ Mount Google Drive
      └─ Load workspace from Drive → WorkspaceManager.load()
            │
            ▼
     Previous workspace state restored ✅
     Previous conversation history available ✅
     AST index available ✅
```

---

## Future Roadmap

| Feature | Status | Notes |
|---|---|---|
| JSON conversation history | ✅ Implemented | Current format |
| AST symbol indexer | ✅ Implemented | Python codebases |
| Google Drive persistence | ✅ Implemented | Colab environments |
| SQLite conversation store | 🔜 Planned v1.3 | Queryable history |
| Multi-language symbol indexer | 🔜 Planned v2.0 | JS, TS, Rust, Java |
| Semantic search over history | 🔜 Planned v2.0 | Embedding-based retrieval |
| Shared workspace over network | 🔜 Planned v2.0 | Team collaboration |
