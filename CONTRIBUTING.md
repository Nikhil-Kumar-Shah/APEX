# Contributing to APEX

Thank you for contributing to **APEX**! We welcome bug reports, feature suggestions, documentation additions, and code improvements.

---

## 🛠️ Local Development Setup

1. **Fork the Repository**: Create a personal fork on GitHub.
2. **Clone Locally**:
   ```bash
   git clone https://github.com/Nikhil-Kumar-Shah/APEX.git
   cd APEX
   ```
3. **Install dependencies**: Install standard packages along with dev testing extras:
   ```bash
   pip install -e .[dev,ml]
   ```

---

## 🌿 Branch Naming & Commits

- **Branch Naming**:
  - Bugs: `fix/issue-description`
  - Features: `feat/feature-description`
  - Docs: `docs/documentation-topic`
- **Commit Style**: We follow **Conventional Commits** guidelines (e.g., `feat: add mistral model profile` or `fix: handle invalid json parsing`).

---

## 🧪 Testing Rules

We require all pull requests to pass the full pytest suite. Run all tests locally before opening a pull request:
```bash
pytest tests/
```

---

## 🚀 Pull Request Checklist

Before submitting a Pull Request:
- [ ] Confirm all unit tests pass locally.
- [ ] Include updated docstrings and types for new Python methods.
- [ ] Document new custom commands or config properties.
- [ ] Maintain semantic version compatibility.
