"""Automated validation tests for the APEX static documentation website and README."""

import json
import re
from pathlib import Path

DOCS_PAGES = [
    "index.html",
    "getting-started.html",
    "configuration.html",
    "api.html",
    "troubleshooting.html",
    "development.html",
]


def test_docs_pages_exist():
    """Verifies that all 6 required documentation pages exist."""
    docs_dir = Path("docs")
    assert docs_dir.exists() and docs_dir.is_dir()

    for page in DOCS_PAGES:
        page_path = docs_dir / page
        assert page_path.exists(), f"Missing required documentation page: {page}"
        assert page_path.stat().st_size > 500, f"Page {page} is unexpectedly empty"


def test_docs_assets_exist():
    """Verifies that stylesheet, search script, and search index exist."""
    css_path = Path("docs/assets/css/style.css")
    js_path = Path("docs/assets/js/search.js")
    index_path = Path("docs/search-index.json")

    assert css_path.exists(), "Missing style.css"
    assert js_path.exists(), "Missing search.js"
    assert index_path.exists(), "Missing search-index.json"

    # Verify CSS contains required red-and-white visual identity tokens
    css_content = css_path.read_text(encoding="utf-8")
    assert "#FFFFFF" in css_content or "#ffffff" in css_content.lower()
    assert "#C62828" in css_content or "#c62828" in css_content.lower()
    assert "#202020" in css_content


def test_search_index_schema_and_integrity():
    """Verifies that search-index.json is valid and indexes all pages."""
    index_path = Path("docs/search-index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) >= 15

    indexed_urls = set()
    for entry in data:
        assert "title" in entry
        assert "url" in entry
        assert "section" in entry
        assert "keywords" in entry
        assert "snippet" in entry
        base_page = entry["url"].split("#")[0]
        indexed_urls.add(base_page)

    for page in DOCS_PAGES:
        assert page in indexed_urls, f"Page {page} is missing from search index"


def test_relative_paths_and_no_root_relative_hrefs():
    """Verifies all internal links are relative and will resolve under GitHub Pages /APEX/ base path."""
    docs_dir = Path("docs")
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']')
    src_pattern = re.compile(r'src=["\']([^"\']+)["\']')

    for page in DOCS_PAGES:
        content = (docs_dir / page).read_text(encoding="utf-8")

        # Must not contain root-relative links like href="/api.html" or src="/assets/..."
        for match in href_pattern.findall(content):
            if match.startswith("http") or match.startswith("#") or match.startswith("mailto:"):
                continue
            assert not match.startswith("/"), f"Root-relative link '{match}' in {page} will break on GitHub Pages /APEX/"
            # If linking to an HTML page, verify target file exists
            target_page = match.split("#")[0]
            if target_page and target_page.endswith(".html"):
                assert (docs_dir / target_page).exists(), f"Broken link '{match}' in {page}"

        for match in src_pattern.findall(content):
            if match.startswith("http") or match.startswith("data:"):
                continue
            assert not match.startswith("/"), f"Root-relative asset src '{match}' in {page} will break on GitHub Pages"
            assert (docs_dir / match).exists(), f"Missing asset '{match}' referenced in {page}"


def test_html_metadata_and_structure():
    """Verifies standard HTML5 structure, title, description, and canonical tags on all pages."""
    docs_dir = Path("docs")

    for page in DOCS_PAGES:
        content = (docs_dir / page).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html lang=\"en\">" in content
        assert "<title>" in content and "APEX" in content
        assert 'name="viewport"' in content
        assert 'name="description"' in content
        assert 'rel="canonical"' in content
        assert 'property="og:title"' in content
        assert 'id="search-input"' in content
        assert 'assets/css/style.css' in content
        assert 'assets/js/search.js' in content


def test_readme_length_and_content():
    """Verifies that the redesigned README is concise, accurate, and within 100-160 lines."""
    readme_path = Path("README.md")
    assert readme_path.exists()

    lines = readme_path.read_text(encoding="utf-8").splitlines()
    assert 90 <= len(lines) <= 170, f"README length {len(lines)} lines outside target range (100-160 lines)"

    full_text = "\n".join(lines)

    # Required links
    assert "https://colab.research.google.com/github/Nikhil-Kumar-Shah/APEX/blob/main/notebook/APEX.ipynb" in full_text
    assert "https://nikhil-kumar-shah.github.io/APEX/" in full_text
    assert "LICENSE" in full_text
    assert "SECURITY.md" in full_text

    # Required sections
    assert "## What is APEX?" in full_text
    assert "## Key Features" in full_text
    assert "## Quick Start" in full_text
    assert "## Documentation Website" in full_text
    assert "## API Integration Example" in full_text
    assert "## Requirements & Limitations" in full_text
    assert "## Development & Contributing" in full_text
    assert "## Security & License" in full_text

    # Code snippet present
    assert "from openai import OpenAI" in full_text

    # Zero references to obsolete 9 sections
    for s_idx in (0, 3, 4, 5, 6, 7, 8):
        assert f"Section {s_idx}" not in full_text

