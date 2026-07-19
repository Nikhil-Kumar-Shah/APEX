"""Log reading and filter presentation utilities."""

import os
from pathlib import Path
from typing import List, Optional


class LogViewer:
    """Parses local log files and returns filtered rows for presentation views."""

    def __init__(self, log_filepath: Path):
        """Initializes the LogViewer.

        Args:
            log_filepath: Path to the active log file (usually logs/runtime.log).
        """
        self.log_filepath = log_filepath

    def fetch_logs(self, limit: int = 100, level_filter: Optional[str] = None, search_query: Optional[str] = None) -> List[str]:
        """Reads log lines from the bottom, applying level or query filters.

        Args:
            limit: Maximum lines to return.
            level_filter: Filter logs matching e.g., 'INFO', 'WARNING', 'ERROR'.
            search_query: Search string keyword match.

        Returns:
            List[str]: List of formatted log strings.
        """
        if not self.log_filepath.is_file():
            return [f"Log file not found at: {self.log_filepath}"]

        try:
            with open(self.log_filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            return [f"Failed to read logs: {e}"]

        filtered_lines = []
        # Search from bottom to top (most recent first)
        for line in reversed(lines):
            line_str = line.strip()
            if not line_str:
                continue

            # Level filter check
            if level_filter:
                level_tag = f"[{level_filter.upper()}]"
                if level_tag not in line_str:
                    continue

            # Query match check
            if search_query:
                if search_query.lower() not in line_str.lower():
                    continue

            filtered_lines.append(line_str)
            if len(filtered_lines) >= limit:
                break

        # Re-reverse so chronological order is restored
        filtered_lines.reverse()
        return filtered_lines
