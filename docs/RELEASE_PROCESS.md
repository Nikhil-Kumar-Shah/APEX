# APEX Release Process Guide

This document outlines the release process for publishing a new stable version of the **APEX** platform.

---

## 📋 Pre-Release Checklist

Ensure the following steps are completed before tag publication:

1. **Verify Unit Tests**: Run `pytest tests/` and confirm all cases are green.
2. **Version Bump**:
   - Update `__version__` in [runtime/__init__.py](file:///d:/colab_ Models/runtime/__init__.py).
   - Update `version` in [pyproject.toml](file:///d:/colab_ Models/pyproject.toml).
   - Update `LATEST_RUNTIME_VERSION` in [updater.py](file:///d:/colab_ Models/runtime/ui/updater.py).
3. **Verify Configuration Mappings**: Ensure that example configurations under `examples/` match the active schemas.
4. **Update Changelog**: Add release notes, dates, and changes to [CHANGELOG.md](file:///d:/colab_ Models/CHANGELOG.md).

---

## 📦 Building Package Distributions

To build and verify source distribution packages:

1. **Install Build Tools**:
   ```bash
   pip install --upgrade build twine
   ```
2. **Compile Tarballs & Wheels**:
   ```bash
   python -m build
   ```
3. **Verify Artifacts**: Check that files are created in the `dist/` directory:
   ```bash
   twine check dist/*
   ```
