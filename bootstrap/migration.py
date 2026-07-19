"""Configuration migration and rollback management."""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from runtime.config.manager import ConfigManager
from runtime.utils.file import safe_read_json, safe_write_json

logger = logging.getLogger("bootstrap.migration")


class MigrationManager:
    """Safely upgrades configurations, creating backups and executing rollbacks on failure."""

    def __init__(self, config_path: Path):
        """Initializes the MigrationManager.

        Args:
            config_path: Path to the JSON configuration file.
        """
        self.config_path = config_path

    @property
    def backup_path(self) -> Path:
        """Determines backup configuration file path."""
        return self.config_path.with_suffix(".config.bak")

    def backup(self) -> bool:
        """Creates a backup file of the active configuration."""
        if not self.config_path.is_file():
            return False
        try:
            shutil.copy(self.config_path, self.backup_path)
            logger.info(f"[+] Backup configuration created at: {self.backup_path}")
            return True
        except OSError as e:
            logger.error(f"[-] Configuration backup failed: {e}")
            return False

    def rollback(self) -> bool:
        """Restores the configuration state from the backup file."""
        if not self.backup_path.is_file():
            return False
        try:
            shutil.copy(self.backup_path, self.config_path)
            logger.info("[+] Configuration rolled back successfully.")
            return True
        except OSError as e:
            logger.error(f"[-] Configuration rollback failed: {e}")
            return False

    def migrate(self) -> bool:
        """Checks schema versions and runs automatic migrations safely."""
        if not self.config_path.is_file():
            return True

        # 1. Create backup before migration
        self.backup()

        try:
            manager = ConfigManager(self.config_path)
            # Load will automatically execute internal schema migration and save it
            manager.load()
            manager.save()
            
            # Remove backup on successful migration
            if self.backup_path.is_file():
                self.backup_path.unlink()
            return True
        except Exception as e:
            logger.error(f"[-] Migration failed: {e}. Executing rollback...")
            self.rollback()
            return False
