# Contributing to APEX

Thank you for your interest in contributing to **APEX**. This project is built by developers for developers, and every contribution — whether a bug fix, new feature, documentation improvement, or test — makes a real difference.

Please read this guide completely before opening a pull request.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Branch Strategy](#branch-strategy)
- [Conventional Commits](#conventional-commits)
- [Testing Requirements](#testing-requirements)
- [Documentation Requirements](#documentation-requirements)
- [Pull Request Workflow](#pull-request-workflow)
- [Review Expectations](#review-expectations)

---

## Code of Conduct

All contributors are expected to uphold the [Code of Conduct](CODE_OF_CONDUCT.md). Harassment, dismissive behaviour, or unprofessional conduct will not be tolerated.

---

## Ways to Contribute

| Type | How |
|---|---|
| 🐛 **Bug reports** | Open a [Bug Report issue](https://github.com/Nikhil-Kumar-Shah/APEX/issues/new?template=bug_report.md) |
| 💡 **Feature requests** | Open a [Feature Request issue](https://github.com/Nikhil-Kumar-Shah/APEX/issues/new?template=feature_request.md) |
| 🔧 **Code changes** | Fork → branch → PR (see below) |
| 📖 **Documentation** | Edit any `docs/` file or the README and open a PR |
| 🧪 **Tests** | Add or improve test coverage in `tests/` |
| 💬 **Discussions** | Share ideas in [GitHub Discussions](https://github.com/Nikhil-Kumar-Shah/APEX/discussions) |

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- A CUDA-capable GPU (optional; CPU inference works but is slow)

### Step-by-step

```bash
# 1. Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/APEX.git
cd APEX

# 2. Add the upstream remote
git remote add upstream https://github.com/Nikhil-Kumar-Shah/APEX.git

# 3. Install the package in editable mode with all dev and ML extras
pip install -e ".[dev,ml]"

# 4. Verify the installation
pytest tests/ -v

# 5. Create your working branch (see Branch Strategy below)
git checkout -b feat/my-feature
```

> **Note:** Always sync with upstream before starting new work.
>
> ```bash
> git fetch upstream
> git rebase upstream/main
> ```

---

## Project Structure

```
APEX/
├── bootstrap/    — Environment bootstrap and deployment
├── runtime/      — Core application runtime
│   ├── api/      — OpenAI-compatible FastAPI server
│   ├── engine/   — Inference engine adapters
│   ├── model/    — Model manager and downloader
│   ├── memory/   — Workspace and conversation state
│   ├── config/   — Configuration schema and loader
│   └── ui/       — Notebook ipywidgets dashboard
├── tests/        — pytest test suite
├── docs/         — Architecture and developer documentation
└── examples/     — Example configuration files
```

See the [Developer Guide](docs/DEVELOPER_GUIDE.md) for a detailed breakdown of every package and its responsibilities.

---

## Coding Standards

### Language

- Python 3.10+ syntax and type hints are required throughout.
- All code must pass `PEP 8` formatting.

### Type Hints

All function signatures must include type hints:

```python
def load_model(model_id: str, device: str = "cuda") -> None:
    ...
```

### Docstrings

All public classes and methods require **Google-style docstrings**:

```python
def generate(self, prompt: str, max_tokens: int = 256) -> str:
    """Generate a text completion for the given prompt.

    Args:
        prompt: The input string to complete.
        max_tokens: Maximum number of tokens to generate.

    Returns:
        The generated completion string.

    Raises:
        RuntimeError: If no model is currently loaded.
    """
```

### Error Handling

- Never expose raw Python tracebacks to API clients.
- Use the `openai_error_response()` helper in `runtime/api/errors.py` for all API error responses.
- Include a human-readable `message`, a `code`, an `error_type`, and a `details.resolution` for every error.

### Logging

Use the structured logger from `runtime/logging/`. Do not use bare `print()` statements in runtime code.

```python
from runtime.logging import get_logger
logger = get_logger(__name__)
logger.info("Model loaded successfully", model_id=model_id)
```

---

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Stable release branch. Only receives tagged releases. |
| `dev` | Integration branch. All PRs merge here first. |
| `feat/*` | New features |
| `fix/*` | Bug fixes |
| `docs/*` | Documentation-only changes |
| `refactor/*` | Code refactoring without behaviour changes |
| `test/*` | New or improved tests |
| `chore/*` | Dependency updates, tooling, CI changes |

**Always branch from `dev`, not `main`.**

```bash
git checkout dev
git pull upstream dev
git checkout -b feat/vllm-backend
```

---

## Conventional Commits

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type | When to use |
|---|---|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructuring without behaviour change |
| `test` | Adding or updating tests |
| `chore` | Tooling, dependencies, CI |
| `perf` | Performance improvements |
| `style` | Formatting only (no logic change) |

### Examples

```bash
git commit -m "feat(api): add WebSocket streaming endpoint"
git commit -m "fix(engine): handle CUDA OOM gracefully with informative error"
git commit -m "docs(readme): update OpenAI compatibility table"
git commit -m "test(api): add chat completions streaming integration test"
git commit -m "chore: bump transformers to 4.42.0"
```

### Breaking Changes

Append `!` after the type and include a `BREAKING CHANGE:` footer:

```bash
git commit -m "feat(config)!: rename 'server' config block to 'api'

BREAKING CHANGE: The 'server' key in apex.config.json must be renamed to 'api'.
Migration is handled automatically by bootstrap/migration.py."
```

---

## Testing Requirements

All pull requests must include tests for new functionality. We use **pytest**.

### Running the test suite

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_api.py -v

# Run with output (useful for debugging)
pytest tests/ -s -v

# Run only tests matching a keyword
pytest tests/ -k "test_chat" -v
```

### Writing tests

- Place tests in `tests/` with the naming convention `test_<module>.py`.
- Use descriptive test function names: `test_chat_completion_returns_openai_format()`.
- Tests must not make real HTTP requests to external services. Use `httpx.AsyncClient` with the FastAPI `TestClient` for API tests.
- New API endpoints must have at minimum: a happy-path test and an error-path test.

---

## Documentation Requirements

If your PR:

| Change | Documentation Required |
|---|---|
| Adds a new API endpoint | Update `docs/API_REFERENCE.md` and the endpoint table in `README.md` |
| Changes config schema | Update `docs/CONFIGURATION.md` |
| Changes the architecture | Update the relevant `docs/*_Architecture.md` file |
| Adds a new module/package | Add it to the repository structure in `README.md` and `docs/DEVELOPER_GUIDE.md` |
| Changes the install process | Update `docs/INSTALLATION.md` |
| Is a new feature | Update `CHANGELOG.md` under `[Unreleased]` |

---

## Pull Request Workflow

1. **Ensure your branch is up to date** with `dev`.
2. **Run the full test suite** locally — all tests must pass.
3. **Open a Pull Request** targeting the `dev` branch.
4. **Fill out the PR template** completely — incomplete PRs may be closed.
5. **Respond to review comments** promptly and push fixup commits.
6. Once approved, a maintainer will **squash-merge** your PR into `dev`.

### PR Title Format

Follow the same Conventional Commits format:

```
feat(api): add vLLM inference backend adapter
fix(workspace): resolve Google Drive mount race condition
```

---

## Review Expectations

- Reviews will be completed within **5 business days** of submission.
- Reviewers will leave inline comments on specific lines — please respond to each one.
- A PR requires **1 maintainer approval** before merge.
- All CI checks (tests) must be green before merge.
- Reviewers may request changes; please address them promptly. PRs with no activity for 14 days may be closed.

---

Thank you for contributing to APEX. 🚀
