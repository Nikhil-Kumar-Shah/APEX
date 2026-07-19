# Memory & Workspace Architecture

The memory system provides persistence across execution sessions. It manages projects workspace preferences, conversation history logs, and indexes codebase structures.

---

## 🏗️ Components

### 1. Workspace Isolation
- **Directories Management**: Creates distinct workspaces on disk (e.g., Google Drive vs. local folders).
- **Project Preferences**: Stores workspace configurations, active models, active engines, and API keys.

### 2. Conversation Loggers
- **History Tracking**: Automatically saves chat completions in structured JSON files.
- **Session Restoration**: Allows clients to query recent history to restore chat context.

### 3. Codebase Indexer
- **AST Parsing**: Scans target source folders, parses python files, and indexes classes, functions, and imports.
- **Workspace Navigation**: Provides codebase search capabilities for downstream developer agents.
