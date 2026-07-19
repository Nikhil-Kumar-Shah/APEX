"""Runtime Lifecycle Management."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.config.manager import ConfigManager
from runtime.core.identity import ProjectIdentity
from runtime.drive.manager import DriveManager
from runtime.logging.logger import setup_logger
from runtime.setup.wizard import SetupWizard
from runtime.utils.env import detect_environment
from runtime.validation.validators import EnvironmentValidator, ValidationError


class RuntimeLifecycle:
    """Orchestrates the startup, validation, and shutdown sequence of the runtime."""

    def __init__(self, workspace_path: Optional[Path] = None):
        """Initializes the RuntimeLifecycle.

        Args:
            workspace_path: Optional path to the local repository workspace.
        """
        self.drive_manager = DriveManager(fallback_local_root=workspace_path)
        self.logger: Optional[logging.Logger] = None
        self.config_manager: Optional[ConfigManager] = None
        self.identity: Optional[ProjectIdentity] = None
        self.is_initialized = False

    def startup(self, interactive: bool = True) -> bool:
        """Executes the entire startup sequence.

        Args:
            interactive: Whether to prompt user interactively if setup is needed.

        Returns:
            bool: True if initialization was successful.
        """
        try:
            # 1. Environment Detection
            env = detect_environment()
            print(f"[+] Detected Environment: {env.upper()}")

            # 2. Drive Mount & Project Detection
            print("[+] Mounting storage drive...")
            if not self.drive_manager.mount():
                print("[-] Error mounting drive. Aborting initialization.")
                return False

            project_root = self.drive_manager.project_root
            print(f"[+] Project Root: {project_root}")

            # 3. Path & Directory Setup
            config_dir = project_root / "configs"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "apex.config.json"


            # 4. Configuration Detection & Setup Wizard
            self.config_manager = ConfigManager(config_file)
            wizard = SetupWizard(self.config_manager)

            if wizard.needs_setup(config_file):
                print("[!] Configuration not found or invalid. Starting setup wizard...")
                setup_success = wizard.run(interactive=interactive)
                if not setup_success:
                    print("[-] Setup wizard failed to complete.")
                    return False

            # Load configuration
            config = self.config_manager.load()

            # 5. Initialize Logging
            log_dir = project_root / config.get("directories", {}).get("log_dir", "logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "runtime.log"

            log_level_str = config.get("logging", {}).get("level", "INFO")
            log_level = getattr(logging, log_level_str, logging.INFO)

            self.logger = setup_logger("runtime", log_file=log_file, level=log_level)
            self.logger.info("=" * 50)
            self.logger.info("Initializing APEX...")

            self.logger.info(f"Environment: {env}")
            self.logger.info(f"Project root resolved to: {project_root}")

            # 6. Initialize Directories
            cache_dir = project_root / config.get("directories", {}).get("cache_dir", "cache")
            output_dir = project_root / config.get("directories", {}).get("output_dir", "outputs")

            # 7. Environment Validation (Checking permissions on required directories)
            self.logger.info("Running environment validations...")
            EnvironmentValidator.validate([project_root, log_dir, cache_dir, output_dir])

            # Ensure all folders exist
            cache_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 8. Load Project Identity
            self.identity = ProjectIdentity.from_config(config)
            self.logger.info(f"Project Loaded: {self.identity.project_name} ({self.identity.project_id})")
            self.logger.info(f"Runtime Version: {self.identity.runtime_version}")
            self.logger.info(f"Configuration Version: {self.identity.config_version}")

            self.is_initialized = True
            self.logger.info("APEX is ready.")

            self.logger.info("=" * 50)
            return True

        except ValidationError as ve:
            if self.logger:
                self.logger.error(f"Validation error during startup: {ve}", exc_info=True)
            else:
                print(f"[-] Validation error during startup: {ve}")
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Fatal error during startup sequence: {e}", exc_info=True)
            else:
                print(f"[-] Fatal error during startup sequence: {e}")
            return False
