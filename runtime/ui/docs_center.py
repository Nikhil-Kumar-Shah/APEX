"""Interactive Documentation Center for APEX — Google Colab / JupyterLab widget.

This module provides a self-contained DocumentationCenter class that:
  - Auto-discovers all Markdown files in docs/ and the repo root.
  - Renders them with professional dark-themed HTML styling.
  - Implements full-text search across the entire documentation set.
  - Displays a live project information panel with git and system metadata.
  - Renders a hero welcome screen.
  - Caches documents in memory for fast navigation.
  - Degrades gracefully if ipywidgets or the markdown library is missing.

Usage (inside a Colab/Jupyter cell):
    from runtime.ui.docs_center import DocumentationCenter
    dc = DocumentationCenter(root_path="/content/APEX")
    dc.render_welcome()
    dc.render()
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import platform
import subprocess
import sys
import textwrap
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("runtime.ui.docs_center")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_APEX_VERSION = "1.2.0"
_REPO_URL = "https://github.com/Nikhil-Kumar-Shah/APEX"
_AUTHOR = "Nikhil Kumar Shah"
_LICENSE = "MIT"

# Pinned nav entries — ordered, with fallback filenames relative to repo root.
# These are shown first in the nav, followed by any auto-discovered extras.
_PINNED_DOCS: List[Tuple[str, str, str]] = [
    ("🏠", "Welcome / README", "README.md"),
    ("📦", "Installation", "docs/INSTALLATION.md"),
    ("⚙️", "Configuration", "docs/CONFIGURATION.md"),
    ("🌐", "API Reference", "docs/API_REFERENCE.md"),
    ("🤖", "Model Runtime", "docs/Model_Runtime_Architecture.md"),
    ("🧠", "Memory & Workspace", "docs/Memory_Workspace_Architecture.md"),
    ("🖥️", "UI Architecture", "docs/User_Interface_Architecture.md"),
    ("🔧", "Server API", "docs/Server_API_Architecture.md"),
    ("👩‍💻", "Developer Guide", "docs/DEVELOPER_GUIDE.md"),
    ("📋", "Release Process", "docs/RELEASE_PROCESS.md"),
    ("🔒", "Security", "SECURITY.md"),
    ("❤️", "Contributing", "CONTRIBUTING.md"),
    ("📜", "Code of Conduct", "CODE_OF_CONDUCT.md"),
    ("📰", "Changelog", "CHANGELOG.md"),
    ("❓", "Support", "SUPPORT.md"),
]

_CSS = """
<style>
/* ── APEX Documentation Center ── */
.apex-portal {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica,
                 Arial, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #30363d;
}
.apex-topbar {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 10px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
}
.apex-topbar-title {
    color: #58a6ff;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.5px;
}
.apex-topbar-badge {
    background: #21262d;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px;
}
.apex-search-box {
    flex: 1;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #c9d1d9;
    padding: 5px 10px;
    font-size: 13px;
    outline: none;
}
.apex-search-box:focus { border-color: #58a6ff; }
.apex-layout {
    display: flex;
    height: 640px;
}
.apex-nav {
    width: 220px;
    min-width: 220px;
    background: #161b22;
    border-right: 1px solid #30363d;
    overflow-y: auto;
    padding: 10px 0;
}
.apex-nav-header {
    color: #8b949e;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 6px 16px 4px;
}
.apex-nav-item {
    padding: 7px 16px;
    cursor: pointer;
    font-size: 12.5px;
    color: #8b949e;
    display: flex;
    align-items: center;
    gap: 8px;
    border-left: 3px solid transparent;
    transition: all 0.12s ease;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.apex-nav-item:hover {
    background: #21262d;
    color: #c9d1d9;
    border-left-color: #30363d;
}
.apex-nav-item.active {
    background: #1f2d3d;
    color: #58a6ff;
    border-left-color: #58a6ff;
    font-weight: 600;
}
.apex-nav-divider {
    height: 1px;
    background: #21262d;
    margin: 8px 0;
}
.apex-content {
    flex: 1;
    overflow-y: auto;
    padding: 28px 36px;
    background: #0d1117;
}
/* ── Markdown-rendered content ── */
.apex-md h1 {
    font-size: 22px; font-weight: 700; color: #e6edf3;
    border-bottom: 1px solid #21262d; padding-bottom: 10px; margin-bottom: 16px;
}
.apex-md h2 {
    font-size: 17px; font-weight: 600; color: #c9d1d9;
    border-bottom: 1px solid #21262d; padding-bottom: 6px; margin: 22px 0 10px;
}
.apex-md h3 { font-size: 14px; font-weight: 600; color: #c9d1d9; margin: 16px 0 8px; }
.apex-md h4 { font-size: 13px; font-weight: 600; color: #8b949e; margin: 12px 0 6px; }
.apex-md p  { line-height: 1.7; margin: 8px 0; font-size: 13.5px; }
.apex-md a  { color: #58a6ff; text-decoration: none; }
.apex-md a:hover { text-decoration: underline; }
.apex-md code {
    background: #21262d; color: #f0883e; border-radius: 4px;
    padding: 1px 6px; font-size: 12px; font-family: "SFMono-Regular", Consolas, monospace;
}
.apex-md pre {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 14px 16px; overflow-x: auto; margin: 10px 0;
}
.apex-md pre code {
    background: none; color: #a5d6ff; padding: 0; font-size: 12px;
    white-space: pre;
}
.apex-md table {
    width: 100%; border-collapse: collapse; font-size: 12.5px; margin: 12px 0;
}
.apex-md th {
    background: #161b22; color: #8b949e; font-weight: 600;
    padding: 7px 12px; border: 1px solid #30363d; text-align: left;
}
.apex-md td {
    padding: 6px 12px; border: 1px solid #21262d; color: #c9d1d9;
    vertical-align: top;
}
.apex-md tr:nth-child(even) td { background: #0d1117; }
.apex-md tr:nth-child(odd) td { background: #161b22; }
.apex-md ul, .apex-md ol {
    padding-left: 22px; margin: 8px 0; line-height: 1.7; font-size: 13.5px;
}
.apex-md li { margin: 3px 0; }
.apex-md blockquote {
    border-left: 3px solid #58a6ff; background: #161b22;
    padding: 10px 16px; margin: 10px 0; border-radius: 0 6px 6px 0;
    color: #8b949e; font-style: italic;
}
.apex-md hr { border: none; border-top: 1px solid #21262d; margin: 18px 0; }
.apex-md img { max-width: 100%; border-radius: 6px; margin: 8px 0; }
/* ── Search results ── */
.apex-search-result {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 10px; cursor: pointer;
}
.apex-search-result:hover { border-color: #58a6ff; }
.apex-search-result-doc { color: #58a6ff; font-size: 11px; font-weight: 600; }
.apex-search-result-title { color: #e6edf3; font-size: 13px; margin: 2px 0; }
.apex-search-result-excerpt { color: #8b949e; font-size: 12px; line-height: 1.5; }
.apex-highlight { background: #3d2b00; color: #e3b341; border-radius: 2px; padding: 0 2px; }
/* ── Welcome hero ── */
.apex-hero {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 36px 40px;
    text-align: center;
    margin-bottom: 20px;
}
.apex-hero-title {
    font-size: 42px; font-weight: 800; letter-spacing: -1px;
    background: linear-gradient(135deg, #58a6ff, #a5d6ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}
.apex-hero-subtitle { color: #8b949e; font-size: 15px; max-width: 540px; margin: 0 auto 12px; }
.apex-hero-slogan { color: #58a6ff; font-size: 13px; font-style: italic; margin-bottom: 20px; }
.apex-hero-divider { border: none; border-top: 1px solid #21262d; margin: 18px auto; max-width: 320px; }
.apex-badge-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 16px; }
.apex-badge { background: #21262d; border: 1px solid #30363d; border-radius: 20px;
    padding: 4px 12px; font-size: 11px; color: #8b949e; }
/* ── Info panel ── */
.apex-info-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px;
}
.apex-info-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 18px;
}
.apex-info-card-title { color: #8b949e; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.apex-info-row { display: flex; justify-content: space-between; font-size: 12px;
    padding: 3px 0; border-bottom: 1px solid #21262d; }
.apex-info-row:last-child { border-bottom: none; }
.apex-info-key { color: #8b949e; }
.apex-info-val { color: #c9d1d9; font-family: monospace; font-size: 11px; }
.apex-info-val.ok { color: #3fb950; }
.apex-info-val.warn { color: #d29922; }
/* ── Quick action buttons ── */
.apex-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
.apex-btn {
    background: #21262d; border: 1px solid #30363d; color: #c9d1d9;
    border-radius: 6px; padding: 8px 16px; font-size: 12.5px; cursor: pointer;
    transition: all 0.12s ease; text-decoration: none; display: inline-block;
}
.apex-btn:hover { background: #30363d; border-color: #58a6ff; color: #58a6ff; }
.apex-btn.primary { background: #1f6feb; border-color: #1f6feb; color: white; }
.apex-btn.primary:hover { background: #388bfd; border-color: #388bfd; }
/* ── Onboarding steps ── */
.apex-step {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 14px 18px; margin-bottom: 8px;
    display: flex; align-items: flex-start; gap: 14px;
}
.apex-step-num {
    background: #21262d; color: #58a6ff; border-radius: 50%;
    width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px; flex-shrink: 0;
}
.apex-step-num.done { background: #1a3a1a; color: #3fb950; }
.apex-step-title { color: #c9d1d9; font-weight: 600; font-size: 13px; }
.apex-step-desc { color: #8b949e; font-size: 12px; margin-top: 3px; line-height: 1.5; }
</style>
"""


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_markdown(text: str) -> str:
    """Convert Markdown text to styled HTML. Uses python-markdown if available."""
    try:
        import markdown  # type: ignore
        html_body = markdown.markdown(
            text,
            extensions=["tables", "fenced_code", "toc", "nl2br", "attr_list", "def_list"],
        )
    except ImportError:
        # Fallback: wrap in <pre> with basic escaping
        escaped = html_lib.escape(text)
        html_body = f"<pre style='white-space:pre-wrap'>{escaped}</pre>"
    return f'<div class="apex-md">{html_body}</div>'


# ---------------------------------------------------------------------------
# System / git info helpers
# ---------------------------------------------------------------------------

def _run(cmd: List[str], cwd: Optional[Path] = None) -> str:
    """Run a subprocess command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _get_git_info(root: Path) -> Dict[str, str]:
    return {
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root) or "unknown",
        "commit": _run(["git", "rev-parse", "--short", "HEAD"], root) or "unknown",
        "commit_count": _run(["git", "rev-list", "--count", "HEAD"], root) or "?",
        "remote": _run(["git", "remote", "get-url", "origin"], root) or _REPO_URL,
    }


def _get_system_info() -> Dict[str, str]:
    info: Dict[str, str] = {
        "python": platform.python_version(),
        "platform": platform.system(),
        "gpu": "N/A",
        "vram": "N/A",
        "ram": "N/A",
        "colab": "No",
    }
    # Google Colab detection
    if "google.colab" in sys.modules:
        info["colab"] = "Yes"
    # GPU
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            info["gpu"] = props.name
            total_vram = props.total_memory / (1024 ** 3)
            used_vram = (props.total_memory - torch.cuda.mem_get_info()[0]) / (1024 ** 3)
            info["vram"] = f"{used_vram:.1f} / {total_vram:.1f} GB"
        else:
            info["gpu"] = "CPU only"
    except ImportError:
        pass
    # RAM
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram"] = f"{mem.used/(1024**3):.1f} / {mem.total/(1024**3):.1f} GB"
    except ImportError:
        pass
    return info


def _fetch_github_meta(repo_url: str) -> Dict[str, str]:
    """Fetch latest release tag from GitHub API (non-blocking background fetch)."""
    try:
        import urllib.request, json as _json
        # Extract owner/repo from URL
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": "APEX-DocCenter/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            return {
                "latest_release": data.get("tag_name", "?"),
                "release_name": data.get("name", ""),
                "release_url": data.get("html_url", ""),
            }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# DocumentationCenter
# ---------------------------------------------------------------------------

class DocumentationCenter:
    """Interactive Documentation Center for the APEX notebook.

    Automatically discovers, caches, and renders all Markdown documentation
    from the repository. Provides a navigation panel, full-text search, and
    a professional dark-themed UI.

    Args:
        root_path: Path to the APEX repository root. Defaults to the parent
                   of this file's parent (i.e. the repo root if installed
                   in the standard layout).
    """

    def __init__(self, root_path: Optional[str | Path] = None):
        if root_path is None:
            # Resolve relative to this file: runtime/ui/docs_center.py → repo root
            root_path = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root_path).resolve()
        self._cache: Dict[str, str] = {}          # label → raw markdown
        self._html_cache: Dict[str, str] = {}     # label → rendered html
        self._nav_entries: List[Tuple[str, str, str]] = []  # (emoji, label, rel_path)
        self._github_meta: Dict[str, str] = {}
        self._discover_docs()
        # Start background GitHub metadata fetch
        threading.Thread(target=self._bg_fetch_github, daemon=True).start()

    # ── Discovery ──────────────────────────────────────────────────────────

    def _discover_docs(self) -> None:
        """Build navigation list from pinned entries + auto-discovered docs/*.md."""
        seen_paths: set[str] = set()
        entries: List[Tuple[str, str, str]] = []

        for emoji, label, rel_path in _PINNED_DOCS:
            abs_path = self.root / rel_path
            if abs_path.exists():
                entries.append((emoji, label, rel_path))
                seen_paths.add(str(abs_path))

        # Auto-discover any additional docs/*.md files
        docs_dir = self.root / "docs"
        if docs_dir.is_dir():
            for md_file in sorted(docs_dir.glob("*.md")):
                if str(md_file) not in seen_paths:
                    label = md_file.stem.replace("_", " ").replace("-", " ").title()
                    entries.append(("📄", label, f"docs/{md_file.name}"))
                    seen_paths.add(str(md_file))

        self._nav_entries = entries
        logger.debug(f"[DocCenter] Discovered {len(entries)} documents.")

    # ── Loading & caching ──────────────────────────────────────────────────

    def _load_doc(self, rel_path: str) -> str:
        """Load and cache a document's raw Markdown text."""
        if rel_path in self._cache:
            return self._cache[rel_path]
        abs_path = self.root / rel_path
        try:
            text = abs_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = f"# Document not found\n\nCould not locate `{rel_path}` relative to `{self.root}`."
        except Exception as exc:
            text = f"# Error reading document\n\n```\n{exc}\n```"
        self._cache[rel_path] = text
        return text

    def _get_html(self, rel_path: str) -> str:
        """Return cached HTML for a doc, rendering from Markdown if needed."""
        if rel_path not in self._html_cache:
            raw = self._load_doc(rel_path)
            self._html_cache[rel_path] = _render_markdown(raw)
        return self._html_cache[rel_path]

    def _prime_cache(self) -> None:
        """Pre-load all documents into memory."""
        for _, _, rel_path in self._nav_entries:
            self._load_doc(rel_path)

    def _bg_fetch_github(self) -> None:
        """Background thread: fetch GitHub release metadata."""
        self._github_meta = _fetch_github_meta(_REPO_URL)

    # ── Search ─────────────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, str]]:
        """Full-text search across all cached documents.

        Args:
            query: Search term (case-insensitive).
            max_results: Maximum number of result items to return.

        Returns:
            List of dicts with keys: doc_label, rel_path, excerpt.
        """
        if not query.strip():
            return []
        self._prime_cache()
        results: List[Dict[str, str]] = []
        q_lower = query.lower()

        for emoji, label, rel_path in self._nav_entries:
            text = self._cache.get(rel_path, "")
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if q_lower in line.lower():
                    # Build excerpt: 2 lines before + matching line + 1 after
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    excerpt = " … ".join(lines[start:end]).strip()
                    if len(excerpt) > 200:
                        idx = excerpt.lower().find(q_lower)
                        excerpt = "…" + excerpt[max(0, idx-60):idx+140] + "…"
                    # Highlight query term
                    highlighted = excerpt.replace(
                        query,
                        f'<span class="apex-highlight">{html_lib.escape(query)}</span>'
                    ).replace(
                        query.lower(),
                        f'<span class="apex-highlight">{html_lib.escape(query.lower())}</span>'
                    )
                    results.append({
                        "doc_label": f"{emoji} {label}",
                        "rel_path": rel_path,
                        "excerpt": highlighted,
                    })
                    if len(results) >= max_results:
                        return results
        return results

    # ── HTML builders ───────────────────────────────────────────────────────

    def _build_nav_html(self, active_path: str = "") -> str:
        items = []
        for emoji, label, rel_path in self._nav_entries:
            active_class = " active" if rel_path == active_path else ""
            safe_path = html_lib.escape(rel_path)
            safe_label = html_lib.escape(label)
            items.append(
                f'<div class="apex-nav-item{active_class}" '
                f'onclick="apexShowDoc(\'{safe_path}\')" title="{safe_label}">'
                f'{emoji} {safe_label}</div>'
            )
        return (
            '<div class="apex-nav-header">Documentation</div>'
            + '<div class="apex-nav-divider"></div>'
            + "\n".join(items)
        )

    def _build_search_results_html(self, query: str) -> str:
        results = self.search(query)
        if not results:
            return (
                f'<div style="color:#8b949e;padding:20px;text-align:center;">'
                f'No results for "<strong>{html_lib.escape(query)}</strong>"</div>'
            )
        parts = [
            f'<div style="color:#8b949e;font-size:11px;margin-bottom:12px;">'
            f'{len(results)} result(s) for "<strong style="color:#e3b341">'
            f'{html_lib.escape(query)}</strong>"</div>'
        ]
        for r in results:
            safe_path = html_lib.escape(r["rel_path"])
            parts.append(
                f'<div class="apex-search-result" onclick="apexShowDoc(\'{safe_path}\')">'
                f'<div class="apex-search-result-doc">{html_lib.escape(r["doc_label"])}</div>'
                f'<div class="apex-search-result-excerpt">{r["excerpt"]}</div>'
                f'</div>'
            )
        return "\n".join(parts)

    # ── Public render methods ───────────────────────────────────────────────

    def render_welcome(self) -> None:
        """Display the APEX hero welcome banner."""
        try:
            from IPython.display import display, HTML
        except ImportError:
            print("APEX — Adaptive Platform for Unified AI Configuration, Orchestration and Workspace Management")
            return

        git = _get_git_info(self.root)
        sys_info = _get_system_info()
        latest = self._github_meta.get("latest_release", f"v{_APEX_VERSION}")

        html = _CSS + f"""
<div class="apex-hero">
  <div class="apex-hero-title">APEX</div>
  <div class="apex-hero-subtitle">
    Adaptive Platform for Unified AI Configuration,<br>Orchestration and Workspace Management
  </div>
  <div class="apex-hero-slogan">
    Configure once. Run any supported AI. Manage everything from one unified workspace.
  </div>
  <hr class="apex-hero-divider">
  <div style="color:#8b949e;font-size:12px;line-height:2;">
    <span style="color:#c9d1d9">Version</span> {html_lib.escape(_APEX_VERSION)} &nbsp;|&nbsp;
    <span style="color:#c9d1d9">Branch</span> {html_lib.escape(git['branch'])} &nbsp;|&nbsp;
    <span style="color:#c9d1d9">Commit</span> {html_lib.escape(git['commit'])} &nbsp;|&nbsp;
    <span style="color:#c9d1d9">License</span> {_LICENSE}<br>
    <a href="{_REPO_URL}" style="color:#58a6ff">⭐ GitHub Repository</a> &nbsp;|&nbsp;
    <span style="color:#c9d1d9">Author</span> {html_lib.escape(_AUTHOR)}
    {'&nbsp;|&nbsp;<span style="color:#3fb950">Latest: ' + html_lib.escape(latest) + '</span>' if latest != '?' else ''}
  </div>
  <div class="apex-badge-row">
    <span class="apex-badge">🐍 Python {sys_info['python']}</span>
    <span class="apex-badge">🔥 PyTorch</span>
    <span class="apex-badge">⚡ FastAPI</span>
    <span class="apex-badge">✅ OpenAI Compatible</span>
    <span class="apex-badge">☁️ Google Colab {'✓' if sys_info['colab'] == 'Yes' else '○'}</span>
    <span class="apex-badge">🎮 GPU: {html_lib.escape(sys_info['gpu'])}</span>
  </div>
</div>
"""
        display(HTML(html))

    def render_system_info(self) -> None:
        """Display the project information panel with system and git metadata."""
        try:
            from IPython.display import display, HTML
        except ImportError:
            return

        git = _get_git_info(self.root)
        sys_info = _get_system_info()

        def row(k: str, v: str, cls: str = "") -> str:
            return (
                f'<div class="apex-info-row">'
                f'<span class="apex-info-key">{k}</span>'
                f'<span class="apex-info-val {cls}">{html_lib.escape(str(v))}</span>'
                f'</div>'
            )

        html = _CSS + f"""
<div class="apex-info-grid">
  <div class="apex-info-card">
    <div class="apex-info-card-title">Project</div>
    {row("Name", "APEX")}
    {row("Version", _APEX_VERSION)}
    {row("Author", _AUTHOR)}
    {row("License", _LICENSE)}
    {row("Repository", _REPO_URL)}
  </div>
  <div class="apex-info-card">
    <div class="apex-info-card-title">Repository</div>
    {row("Branch", git['branch'])}
    {row("Commit", git['commit'])}
    {row("Total Commits", git['commit_count'])}
    {row("Remote", git['remote'][:40] + '...' if len(git['remote']) > 40 else git['remote'])}
  </div>
  <div class="apex-info-card">
    <div class="apex-info-card-title">Runtime Environment</div>
    {row("Python", sys_info['python'])}
    {row("Platform", sys_info['platform'])}
    {row("Google Colab", sys_info['colab'], 'ok' if sys_info['colab'] == 'Yes' else '')}
    {row("GPU", sys_info['gpu'], 'ok' if sys_info['gpu'] not in ('N/A','CPU only') else 'warn')}
    {row("VRAM", sys_info['vram'])}
    {row("RAM", sys_info['ram'])}
  </div>
  <div class="apex-info-card">
    <div class="apex-info-card-title">Documentation</div>
    {row("Docs Found", str(len(self._nav_entries)))}
    {row("docs/ path", str(self.root / 'docs'))}
    {row("Latest Release", self._github_meta.get('latest_release', 'Fetching...'))}
  </div>
</div>
"""
        display(HTML(html))

    def render_quick_actions(self) -> None:
        """Render quick-action buttons for common docs and runtime operations."""
        try:
            from IPython.display import display, HTML
        except ImportError:
            return

        actions_html = _CSS + """
<div class="apex-actions">
  <button class="apex-btn primary" onclick="apexShowDoc('README.md')">🏠 Open README</button>
  <button class="apex-btn" onclick="apexShowDoc('docs/API_REFERENCE.md')">🌐 API Reference</button>
  <button class="apex-btn" onclick="apexShowDoc('docs/DEVELOPER_GUIDE.md')">👩‍💻 Developer Guide</button>
  <button class="apex-btn" onclick="apexShowDoc('docs/INSTALLATION.md')">📦 Installation</button>
  <button class="apex-btn" onclick="apexShowDoc('CHANGELOG.md')">📰 Changelog</button>
  <button class="apex-btn" onclick="apexShowDoc('SECURITY.md')">🔒 Security</button>
</div>
<div style="color:#8b949e;font-size:11px;margin-bottom:8px;">
  💡 Tip: Open the <strong style="color:#c9d1d9">📚 Documentation Center</strong> cell below for interactive browsing and search.
</div>
"""
        display(HTML(actions_html))

    def render(self) -> Any:
        """Render the full interactive Documentation Center widget.

        Returns:
            The rendered ipywidgets widget, or None on graceful degradation.
        """
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            # Graceful degradation: render plain Markdown
            try:
                from IPython.display import display, Markdown
                for _, label, rel_path in self._nav_entries:
                    raw = self._load_doc(rel_path)
                    display(Markdown(f"---\n## {label}\n{raw}"))
            except ImportError:
                for _, label, rel_path in self._nav_entries:
                    print(f"\n{'='*60}\n{label}\n{'='*60}\n{self._load_doc(rel_path)}\n")
            return None

        # Pre-load all docs into cache
        self._prime_cache()

        # Build initial nav + first doc HTML
        first_path = self._nav_entries[0][2] if self._nav_entries else ""
        nav_html = self._build_nav_html(active_path=first_path)
        doc_html = self._get_html(first_path) if first_path else "<em>No documents found.</em>"

        # Encode all docs as JSON for client-side switching
        docs_json_data = {rel_path: self._get_html(rel_path) for _, _, rel_path in self._nav_entries}
        nav_entries_json = [
            {"emoji": e, "label": l, "path": p} for e, l, p in self._nav_entries
        ]
        docs_json_str = json.dumps(docs_json_data)
        nav_entries_str = json.dumps(nav_entries_json)

        portal_id = "apex-portal-" + str(id(self))

        full_html = _CSS + f"""
<div class="apex-portal" id="{portal_id}">
  <div class="apex-topbar">
    <span class="apex-topbar-title">📚 APEX Documentation Center</span>
    <span class="apex-topbar-badge">v{html_lib.escape(_APEX_VERSION)}</span>
    <span class="apex-topbar-badge">{len(self._nav_entries)} docs</span>
    <input class="apex-search-box" id="{portal_id}-search" type="text" 
           placeholder="🔍  Search documentation..." 
           oninput="apexSearch_{portal_id}(this.value)" />
  </div>
  <div class="apex-layout">
    <div class="apex-nav" id="{portal_id}-nav">{nav_html}</div>
    <div class="apex-content apex-md" id="{portal_id}-content">{doc_html}</div>
  </div>
</div>

<script>
(function() {{
  const PORTAL_ID = "{portal_id}";
  const docs = {docs_json_str};
  const navEntries = {nav_entries_str};

  function apexShowDoc(path) {{
    const content = document.getElementById(PORTAL_ID + '-content');
    const nav = document.getElementById(PORTAL_ID + '-nav');
    if (!content) return;
    // Update content
    content.innerHTML = docs[path] || '<em>Document not found: ' + path + '</em>';
    // Update active nav item
    const items = nav.querySelectorAll('.apex-nav-item');
    items.forEach(item => {{
      item.classList.remove('active');
      if (item.getAttribute('onclick') && item.getAttribute('onclick').includes("'" + path + "'")) {{
        item.classList.add('active');
      }}
    }});
    // Scroll to top
    content.scrollTop = 0;
  }}
  // Attach to window so onclick handlers can find it
  window.apexShowDoc = apexShowDoc;

  function apexSearch_{portal_id}(query) {{
    const content = document.getElementById(PORTAL_ID + '-content');
    if (!query || query.trim() === '') {{
      // Restore last active doc
      const activeItem = document.querySelector('#{portal_id}-nav .apex-nav-item.active');
      if (activeItem) {{
        const onclick = activeItem.getAttribute('onclick');
        const match = onclick.match(/apexShowDoc\\'(.*?)\\'/);
        if (match) {{ apexShowDoc(match[1]); return; }}
      }}
      return;
    }}
    // Client-side substring search across all docs
    const q = query.toLowerCase();
    const results = [];
    for (const entry of navEntries) {{
      const docHtml = docs[entry.path] || '';
      // Strip tags for search
      const tmp = document.createElement('div');
      tmp.innerHTML = docHtml;
      const text = tmp.textContent || '';
      const lines = text.split('\\n');
      for (const line of lines) {{
        if (line.toLowerCase().includes(q) && results.length < 15) {{
          const hi = line.replace(
            new RegExp('(' + query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi'),
            '<span class="apex-highlight">$1</span>'
          );
          results.push(`
            <div class="apex-search-result" onclick="apexShowDoc('${{entry.path}}')">
              <div class="apex-search-result-doc">${{entry.emoji}} ${{entry.label}}</div>
              <div class="apex-search-result-excerpt">${{hi}}</div>
            </div>`);
        }}
      }}
    }}
    const header = `<div style="color:#8b949e;font-size:11px;margin-bottom:12px;">
      ${{results.length}} result(s) for "<strong style="color:#e3b341">${{query}}</strong>"</div>`;
    content.innerHTML = results.length > 0
      ? header + results.join('')
      : `<div style="color:#8b949e;padding:40px;text-align:center;">
           No results for "<strong>${{query}}</strong>"</div>`;
  }}
}})();
</script>
"""
        out = widgets.Output()
        with out:
            display(HTML(full_html))
        display(out)
        return out

    def render_onboarding_steps(self, completed: Optional[List[int]] = None) -> None:
        """Render the interactive onboarding tutorial progress tracker.

        Args:
            completed: List of step numbers (1-indexed) that are complete.
                       E.g., [1, 2] means steps 1 and 2 are checked.
        """
        try:
            from IPython.display import display, HTML
        except ImportError:
            return

        if completed is None:
            completed = []

        steps = [
            ("Mount Google Drive", "Grants APEX persistent storage across Colab sessions. Your workspace, configs, and history survive session resets."),
            ("Clone Repository", "Fetches the latest APEX code from GitHub. Run once; subsequent runs perform `git pull` to update."),
            ("Configure Runtime", "Set your model ID, precision, transport, and authentication options in the Configuration cell."),
            ("Download Model", "Downloads the model weights from Hugging Face Hub. Stored in your Drive cache for reuse."),
            ("Load Model", "Allocates model weights into VRAM. Check the dashboard for memory usage."),
            ("Launch API Server", "Starts the FastAPI server and creates a public HTTPS tunnel. Copy the URL to connect your IDE or client."),
        ]

        items = []
        for i, (title, desc) in enumerate(steps, start=1):
            done = i in completed
            num_class = "done" if done else ""
            num_icon = "✓" if done else str(i)
            items.append(f"""
<div class="apex-step">
  <div class="apex-step-num {num_class}">{num_icon}</div>
  <div>
    <div class="apex-step-title">Step {i}: {html_lib.escape(title)}</div>
    <div class="apex-step-desc">{html_lib.escape(desc)}</div>
  </div>
</div>""")

        from IPython.display import display, HTML
        display(HTML(_CSS + "\n".join(items)))
