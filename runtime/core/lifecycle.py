"""Runtime Lifecycle Management."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from runtime.config.manager import ConfigManager
from runtime.core.identity import ProjectIdentity
from runtime.drive.manager import DriveManager
from runtime.logging.logger import setup_logger
from runtime.setup.wizard import SetupWizard
from runtime.utils.env import detect_environment
from runtime.validation.validators import EnvironmentValidator, ValidationError

logger = logging.getLogger("runtime.lifecycle")


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

    def startup(
        self,
        interactive: bool = True,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Executes the entire startup sequence.

        Args:
            interactive: Whether to prompt user interactively if setup is needed.
            on_progress: Optional callback to notify granular sub-operation progress.

        Returns:
            bool: True if initialization was successful.
        """
        try:
            # 1. Environment Detection
            if on_progress:
                on_progress("[1/7] Detecting runtime environment...")
            env = detect_environment()
            logger.info(f"Detected Environment: {env.upper()}", extra={"prefix": "SYSTEM"})

            # 2. Drive Mount & Project Detection
            if on_progress:
                on_progress("[2/7] Verifying persistent storage & Google Drive...")
            logger.info("Mounting storage drive...", extra={"prefix": "SYSTEM"})
            if not self.drive_manager.mount():
                logger.warning(
                    f"Google Drive is not mounted. Proceeding with EPHEMERAL local VM storage ({self.drive_manager.persistence_root}). "
                    "Models and outputs will not persist across Colab session restarts.",
                    extra={"prefix": "STORAGE"},
                )
            else:
                logger.info(
                    f"Storage initialized: Persistent root at {self.drive_manager.persistence_root}",
                    extra={"prefix": "STORAGE"},
                )

            project_root = self.drive_manager.project_root
            logger.info(f"Project Root: {project_root}", extra={"prefix": "SYSTEM"})

            # 3. Path & Directory Setup
            if on_progress:
                on_progress("[3/7] Resolving workspace and project directories...")
            persistence_root = self.drive_manager.persistence_root
            logger.info(f"Persistence Root: {persistence_root}", extra={"prefix": "SYSTEM"})

            # Always initialize the config from persistence root (Google Drive if mounted)
            config_dir = persistence_root / "workspaces" / "default"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"

            # 4. Configuration Detection & Setup Wizard
            if on_progress:
                on_progress("[4/7] Validating runtime configuration...")
            self.config_manager = ConfigManager(config_file)
            wizard = SetupWizard(self.config_manager)

            if wizard.needs_setup(config_file):
                logger.warning("Configuration not found or invalid. Starting setup wizard...", extra={"prefix": "WARNING"})
                setup_success = wizard.run(interactive=interactive)
                if not setup_success:
                    logger.error("Setup wizard failed to complete.", extra={"prefix": "ERROR"})
                    return False

            # Load configuration
            config = self.config_manager.load()

            # 5. Initialize Logging
            if on_progress:
                on_progress("[5/7] Initializing runtime logging infrastructure...")
            log_dir = persistence_root / config.get("directories", {}).get("log_dir", "logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "runtime.log"

            log_level_str = config.get("logging", {}).get("level", "INFO")
            log_level = getattr(logging, log_level_str, logging.INFO)

            self.logger = setup_logger("runtime", log_file=log_file, level=log_level)
            self.logger.info("=" * 50, extra={"prefix": "SYSTEM"})
            self.logger.info("Initializing APEX...", extra={"prefix": "SYSTEM"})

            self.logger.info(f"Environment: {env}", extra={"prefix": "SYSTEM"})
            self.logger.info(f"Project root resolved to: {project_root}", extra={"prefix": "SYSTEM"})

            # 6. Initialize Directories (Cache is ephemeral in VM, Output is persistent)
            if on_progress:
                on_progress("[6/7] Validating filesystem directory permissions...")
            cache_dir = project_root / config.get("directories", {}).get("cache_dir", "cache")
            output_dir = persistence_root / config.get("directories", {}).get("output_dir", "outputs")

            # 7. Environment Validation (Checking permissions on required directories)
            self.logger.info("Running environment validations...", extra={"prefix": "SYSTEM"})
            EnvironmentValidator.validate([project_root, persistence_root, log_dir, cache_dir, output_dir])

            # Ensure all folders exist
            cache_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 8. Load Project Identity
            if on_progress:
                on_progress("[7/7] Loading project identity and default workspace...")
            self.identity = ProjectIdentity.from_config(config)
            self.logger.info(f"Project Loaded: {self.identity.project_name} ({self.identity.project_id})", extra={"prefix": "SYSTEM"})
            self.logger.info(f"Runtime Version: {self.identity.runtime_version}", extra={"prefix": "SYSTEM"})
            self.logger.info(f"Configuration Version: {self.identity.config_version}", extra={"prefix": "SYSTEM"})

            self.is_initialized = True
            self.logger.info("APEX is ready.", extra={"prefix": "SUCCESS"})

            self.logger.info("=" * 50, extra={"prefix": "SYSTEM"})
            return True

        except ValidationError as ve:
            logger.error(f"Validation error during startup: {ve}", exc_info=True, extra={"prefix": "ERROR"})
            return False
        except Exception as e:
            logger.error(f"Fatal error during startup sequence: {e}", exc_info=True, extra={"prefix": "ERROR"})
            return False
