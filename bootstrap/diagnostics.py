"""Environment, Git, and Legacy codebase diagnostics."""

import logging
import subprocess
from pathlib import Path

# Since logger might not be fully initialized via runtime during bootstrap,
# we use the standard logging, but it will be attached to APEX Log Manager later.
logger = logging.getLogger("bootstrap.diagnostics")


class DiagnosticsManager:
    """Runs repository self-diagnostics and version reporting."""

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

    def run_diagnostics(self) -> bool:
        """Executes all diagnostic checks.

        Returns:
            bool: True if diagnostics pass without critical errors.
        """
        logger.info("Running APEX Environment Diagnostics...", extra={"prefix": "SYSTEM"})
        
        self._report_git_status()
        self._check_legacy_patterns()
        
        return True

    def _report_git_status(self) -> None:
        """Logs current branch, commit, and tags."""
        try:
            branch = subprocess.run(
                ["git", "-C", str(self.target_dir), "branch", "--show-current"], 
                capture_output=True, text=True
            ).stdout.strip()
            
            commit = subprocess.run(
                ["git", "-C", str(self.target_dir), "rev-parse", "HEAD"], 
                capture_output=True, text=True
            ).stdout.strip()
            
            tags = subprocess.run(
                ["git", "-C", str(self.target_dir), "tag"], 
                capture_output=True, text=True
            ).stdout.strip().split()
            
            logger.info(f"Repository Path: {self.target_dir.resolve()}", extra={"prefix": "SYSTEM"})
            logger.info(f"Current Branch : {branch}", extra={"prefix": "SYSTEM"})
            logger.info(f"Current Commit : {commit}", extra={"prefix": "SYSTEM"})
            logger.info(f"Git Tags       : {tags if tags else 'None'}", extra={"prefix": "SYSTEM"})
            
        except Exception as e:
            logger.warning(f"Git Diagnostics failed: {e}", extra={"prefix": "WARNING"})

    def _check_legacy_patterns(self) -> None:
        """Scans codebase for old architecture patterns."""
        logger.info("Scanning repository for legacy patterns...", extra={"prefix": "SYSTEM"})
        legacy_detected = False
        
        try:
            for p in self.target_dir.rglob("*"):
                if p.is_file() and p.suffix in [".py", ".md", ".json"] and ".git" not in p.parts and "__pycache__" not in p.parts:
                    try:
                        content = p.read_text(encoding="utf-8")
                        if "v1.0.0" in content and "version_manager.py" in p.name:
                            logger.warning(f"Found legacy tag ref 'v1.0.0' in: {p.relative_to(self.target_dir)}", extra={"prefix": "WARNING"})
                            legacy_detected = True
                        if "configs" in content and "repository_manager.py" in p.name:
                            logger.warning(f"Found legacy hardcoded folder 'configs' in: {p.relative_to(self.target_dir)}", extra={"prefix": "WARNING"})
                            legacy_detected = True
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Self-diagnostics scan failed: {e}", extra={"prefix": "WARNING"})
            
        if not legacy_detected:
            logger.info("Self-diagnostics completed. No active legacy patterns found.", extra={"prefix": "SUCCESS"})
