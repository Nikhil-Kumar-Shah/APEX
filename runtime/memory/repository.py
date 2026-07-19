"""Codebase repository indexing and structural symbol extraction."""

import ast
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.utils.file import safe_read_json, safe_write_json
from runtime.memory.errors import RepositoryUnavailableError


class RepositoryIndexer:
    """Discovers, indexes, tracks changes, and extracts structural symbols from repositories."""

    SUFFIX_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".go": "Go",
        ".rs": "Rust",
        ".cpp": "C++",
        ".h": "C++ Header",
        ".c": "C",
        ".java": "Java",
        ".sh": "Shell",
        ".md": "Markdown",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
    }

    def __init__(self, workspace_path: Path):
        """Initializes the RepositoryIndexer.

        Args:
            workspace_path: Path of the active workspace.
        """
        self.workspace_path = workspace_path
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    @property
    def repos_dir(self) -> Path:
        """Gets the repository indexes directory."""
        return self.workspace_path / "repositories"

    def _get_index_path(self, repo_id: str) -> Path:
        return self.repos_dir / f"{repo_id}.index.json"

    def detect_language(self, file_path: Path) -> str:
        """Determines programming language based on file suffix."""
        return self.SUFFIX_MAP.get(file_path.suffix.lower(), "Unknown")

    def _calculate_md5(self, file_path: Path) -> str:
        """Helper to calculate md5 checksums."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except OSError:
            return ""

    def _extract_symbols(self, file_path: Path, language: str) -> Dict[str, List[str]]:
        """Parses classes, functions, and symbols from source files."""
        symbols = {"classes": [], "functions": [], "imports": []}
        
        if language != "Python" or not file_path.exists():
            return symbols

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols["classes"].append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    symbols["functions"].append(node.name)
                elif isinstance(node, ast.Import):
                    for name in node.names:
                        symbols["imports"].append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        symbols["imports"].append(node.module)
        except Exception:
            # Shield parser issues from breaking indexing
            pass
        return symbols

    def index_repository(self, repo_id: str, local_path: Path) -> Dict[str, Any]:
        """Scans and indexes all files inside a local repository workspace.

        Args:
            repo_id: Unique repository identifier.
            local_path: Absolute directory to scan.

        Returns:
            Dict[str, Any]: The finalized repository index payload.
        """
        if not local_path.is_dir():
            raise RepositoryUnavailableError(str(local_path), "Target directory does not exist.")

        logger_info = {"repo_id": repo_id, "path": str(local_path)}

        # Load existing index for change detection
        index_file = self._get_index_path(repo_id)
        existing_index = safe_read_json(index_file) or {"files": {}}
        existing_files = existing_index.get("files", {})

        new_files = {}
        total_size = 0

        # Scan directory recursively (excluding common build/cache folders)
        exclude_dirs = {".git", "__pycache__", "node_modules", "venv", ".venv", "build", "dist"}

        for root, dirs, files in os.walk(local_path):
            # Prune directories in-place to avoid searching excluded folders
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                f_path = Path(root) / file
                try:
                    rel_path = str(f_path.relative_to(local_path))
                    stat = f_path.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size
                    total_size += size

                    # Change detection: verify against cached mtime
                    existing_entry = existing_files.get(rel_path, {})
                    if existing_entry and existing_entry.get("mtime") == mtime:
                        new_files[rel_path] = existing_entry
                    else:
                        lang = self.detect_language(f_path)
                        symbols = self._extract_symbols(f_path, lang)
                        md5_hash = self._calculate_md5(f_path)

                        new_files[rel_path] = {
                            "path": rel_path,
                            "size_bytes": size,
                            "mtime": mtime,
                            "language": lang,
                            "symbols": symbols,
                            "hash": md5_hash,
                        }
                except (OSError, ValueError):
                    pass

        index_data = {
            "repository_id": repo_id,
            "local_path": str(local_path),
            "total_files": len(new_files),
            "total_size_bytes": total_size,
            "last_indexed_at": time.time(),
            "files": new_files,
        }

        success = safe_write_json(index_file, index_data)
        if not success:
            raise OSError(f"Could not save repository index for '{repo_id}'")

        return index_data

    def load_index(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Loads repository index from disk.

        Args:
            repo_id: Unique repository identifier.

        Returns:
            Optional[Dict[str, Any]]: Repository index payload or None.
        """
        index_file = self._get_index_path(repo_id)
        return safe_read_json(index_file)
