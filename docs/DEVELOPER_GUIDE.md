# APEX Developer Guide

Welcome to the **APEX** Developer Guide! This document provides information on codebase structure, coding guidelines, testing rules, and release cycles to help contributors get started quickly.

---

## 🏗️ Repository Packages

The codebase is split into two packages:

### 1. `bootstrap/` (Deployment Layer)
Manages the environment setup and updates:
- `config.py`: Centralizes repository URL, default branches, and manifest check files.
- `repository_manager.py`: Handles git clone/pull subprocesses.
- `dependency_manager.py`: Runs automated `pip` installations.
- `version_manager.py`: Checks Git tags dynamically and falls back to Development Mode.
- `installer.py`: Standard setup wizard.
- `launcher.py`: Path configurer loading packages dynamically.
- `migration.py`: Handles configuration file backup and schema updates.
- `validator.py`: Performs manifest-based structure validations.

### 2. `runtime/` (Core Application)
- `config`: Handles workspace configuration schemas and migrations.
- `core`: Controls system health, exceptions, and lifecycle startup.
- `drive`: Handles Google Drive mount points.
- `engine`: Manages inference engines (vLLM, Transformers, llama.cpp).
- `logging`: File/console logging with ANSI colors.
- `memory`: Manages workspace state, history tracking, and symbol indexing.
- `server`: Exposes OpenAI-compatible REST API endpoints.
- `ui`: Notebook control widgets using `ipywidgets`.

---

## 🎨 Coding Guidelines & Quality Standards

- **Python Requirements**: Standard PEP 8 coding style with clear type hints.
- **Docstrings**: Google-style docstrings are required for all public methods and classes:
  ```python
  def run_query(self, prompt: str) -> str:
      """Executes model text generation.

      Args:
          prompt: input prompt string.

      Returns:
          str: Completed string.
      """
  ```

---

## 🧪 Testing

We enforce testing across all features. Execute all test suites locally with:
```bash
pytest tests/
```
To run tests with verbose print logs displayed:
```bash
pytest tests/ -s -v
```
