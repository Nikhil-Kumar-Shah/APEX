# APEX Release Process Guide

**Audience:** Maintainers responsible for tagging and publishing APEX releases.
**Purpose:** This document defines the complete release workflow — versioning policy, pre-release checklist, build, tagging, GitHub Release publication, and post-release steps.

---

## Versioning Policy

APEX uses [Semantic Versioning](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

| Component | When to increment |
|---|---|
| **MAJOR** | Breaking changes to the API contract, config schema, or runtime behaviour |
| **MINOR** | New backwards-compatible features (new endpoint, new engine, new config key) |
| **PATCH** | Backwards-compatible bug fixes and security patches |

**Pre-release versions** use the suffix `-alpha.N`, `-beta.N`, or `-rc.N`:
- `1.3.0-alpha.1` — early development, not for general use
- `1.3.0-rc.1` — release candidate, ready for final testing

---

## Release Branches

| Branch | Purpose |
|---|---|
| `main` | Stable releases only. Each commit on main corresponds to a tag. |
| `dev` | Integration branch. All features merge here first. |

The release process always flows: `dev` → review → `main` → tag.

---

## Pre-Release Checklist

Complete every item before tagging a release. No exceptions.

### Code Quality
- [ ] All CI tests passing on `dev` (`pytest tests/ -v` returns 0 failures)
- [ ] No known critical or high-severity bugs open in GitHub Issues
- [ ] All planned features for this release are merged to `dev`
- [ ] No `TODO` or `FIXME` comments introduced in this release cycle

### Version Bumps
Update the version number in **all three** of these locations:

- [ ] `runtime/__init__.py` — `__version__ = "X.Y.Z"`
- [ ] `pyproject.toml` — `version = "X.Y.Z"`
- [ ] Any version constant in the updater / version manager

```bash
# Verify they match
grep -r "__version__\|\"version\"" runtime/__init__.py pyproject.toml
```

### Documentation
- [ ] `CHANGELOG.md` updated — move items from `[Unreleased]` to `[X.Y.Z] — YYYY-MM-DD`
- [ ] `README.md` version badge updated
- [ ] `docs/API_REFERENCE.md` reflects any new or changed endpoints
- [ ] `docs/CONFIGURATION.md` reflects any new or changed config keys
- [ ] Example configs in `examples/` validated against the active schema

### Configuration Compatibility
- [ ] Example configs in `examples/` match the current schema
- [ ] The migration script in `bootstrap/migration.py` handles upgrades from the previous version
- [ ] `config_version` in the schema validator is updated if the schema changed

---

## Building Distribution Packages

```bash
# 1. Install build tools
pip install --upgrade build twine

# 2. Clean any previous build artifacts
rm -rf dist/ build/ *.egg-info

# 3. Build source distribution and wheel
python -m build

# 4. Verify the artifacts are well-formed
twine check dist/*
```

Verify the `dist/` directory contains:
- `apex_runtime-X.Y.Z.tar.gz` — source distribution
- `apex_runtime-X.Y.Z-py3-none-any.whl` — wheel

---

## Merging to main

```bash
# Ensure dev is clean and tests pass
git checkout dev
git pull upstream dev
pytest tests/ -v

# Merge dev into main (no fast-forward, preserve merge commit)
git checkout main
git pull upstream main
git merge --no-ff dev -m "chore: merge dev into main for vX.Y.Z release"

# Push main
git push upstream main
```

---

## Tagging the Release

Tags must be annotated and signed (if GPG key is configured):

```bash
# Create annotated tag
git tag -a vX.Y.Z -m "Release vX.Y.Z

See CHANGELOG.md for full release notes."

# Push the tag
git push upstream vX.Y.Z
```

Tag naming convention:
- Stable release: `v1.2.0`
- Release candidate: `v1.3.0-rc.1`
- Alpha: `v1.3.0-alpha.1`

---

## Publishing the GitHub Release

1. Go to [GitHub Releases](https://github.com/Nikhil-Kumar-Shah/APEX/releases) → **Draft a new release**.
2. Select the tag `vX.Y.Z`.
3. Set the release title: `APEX vX.Y.Z — <short description>`.
4. Copy the relevant section from `CHANGELOG.md` into the release body.
5. Attach the built wheel and source distribution from `dist/`.
6. For pre-releases, check **Set as a pre-release**.
7. For stable releases, check **Set as the latest release**.
8. Click **Publish release**.

---

## Publishing to PyPI (when ready)

```bash
# Upload to PyPI (requires PyPI credentials / token)
twine upload dist/*
```

> **Note:** PyPI publication is planned for v1.3.0. Until then, installation is via `pip install -e .` from the repository.

---

## Post-Release Steps

- [ ] Verify the GitHub Release page is correct.
- [ ] Update `[Unreleased]` section in `CHANGELOG.md` with a fresh empty block.
- [ ] Announce the release in GitHub Discussions.
- [ ] Close any GitHub Issues tagged for this milestone.
- [ ] Open the next milestone on GitHub Issues if appropriate.

---

## Hotfix / Patch Release Process

For urgent bug fixes that cannot wait for the next minor release:

```bash
# Branch off the previous release tag, not dev
git checkout vX.Y.Z
git checkout -b fix/critical-bug-description

# Make the fix, write a test, update CHANGELOG
# ...

# Merge back to main (not dev)
git checkout main
git merge --no-ff fix/critical-bug-description
git tag -a vX.Y.Z+1 -m "Hotfix: <description>"
git push upstream main vX.Y.Z+1

# Backport the fix to dev as well
git checkout dev
git cherry-pick <fix commit hash>
git push upstream dev
```
