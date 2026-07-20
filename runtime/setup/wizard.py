"""Setup Wizard for configuring the Universal Colab Runtime."""

import sys
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.config.manager import ConfigManager
from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE
from runtime.validation.validators import ConfigValidator, ValidationError

logger = logging.getLogger("runtime.setup")


class SetupWizard:
    """Orchestrates configuration wizardry for first-time startup."""

    def __init__(self, config_manager: ConfigManager):
        """Initializes SetupWizard.

        Args:
            config_manager: The ConfigManager instance.
        """
        self.config_manager = config_manager

    @staticmethod
    def needs_setup(config_path: Path) -> bool:
        """Determines if the project needs configuration setup.

        Args:
            config_path: Path to the configuration JSON file.

        Returns:
            bool: True if configuration file is missing or invalid.
        """
        if not config_path.is_file():
            return True

        # Check if it contains valid minimal configuration
        manager = ConfigManager(config_path)
        try:
            manager.load()
            return False
        except (ValidationError, Exception):
            return True

    def run(self, interactive: bool = True, custom_answers: Optional[Dict[str, Any]] = None) -> bool:
        """Runs the setup wizard, prompts for input, and saves config.

        Args:
            interactive: If True, prompt via stdin.
            custom_answers: Preset dictionary to skip interactive prompts.

        Returns:
            bool: True if setup completed and configuration saved successfully.
        """
        answers = DEFAULT_CONFIG_TEMPLATE.copy()
        if custom_answers:
            answers.update(custom_answers)

        logger.info("=" * 50, extra={"prefix": "SYSTEM"})
        logger.info("Universal Colab Runtime Setup", extra={"prefix": "SYSTEM"})
        logger.info("=" * 50, extra={"prefix": "SYSTEM"})

        if not interactive or not sys.stdin.isatty():
            if not interactive:
                logger.info("Running in non-interactive mode. Generating defaults...", extra={"prefix": "SYSTEM"})
            else:
                logger.info("Interactive terminal not detected. Generating defaults...", extra={"prefix": "SYSTEM"})
            try:
                ConfigValidator.validate(answers)
                return self.config_manager.save(answers)
            except ValidationError as e:
                logger.error(f"Validation error on default values: {e}", extra={"prefix": "ERROR"})
                return False

        # Interactive setup
        questions = [
            ("project_id", "Project ID (lowercase slug, e.g. my-project)", answers["project_id"]),
            ("project_name", "Project Name (e.g. My Colab Workspace)", answers["project_name"]),
        ]

        for key, description, default in questions:
            while True:
                try:
                    user_input = input(f"{description} [{default}]: ").strip()
                    val = user_input if user_input else default

                    # Temporary validation on single field if needed
                    temp_answers = answers.copy()
                    temp_answers[key] = val
                    ConfigValidator.validate(temp_answers)

                    # Update answers if validation passes
                    answers[key] = val
                    break
                except ValidationError as e:
                    logger.warning(f"Invalid input: {e}. Please try again.", extra={"prefix": "WARNING"})
                except (KeyboardInterrupt, EOFError):
                    logger.warning("Setup cancelled by user. Using default template configuration.", extra={"prefix": "WARNING"})
                    break

        # Ask about default logging level
        log_level_prompt = input("Default Logging Level (DEBUG, INFO, WARNING, ERROR) [INFO]: ").strip().upper()
        if log_level_prompt in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            answers["logging"]["level"] = log_level_prompt

        try:
            ConfigValidator.validate(answers)
            success = self.config_manager.save(answers)
            if success:
                logger.info(f"Configuration successfully written to: {self.config_manager.config_path}", extra={"prefix": "SUCCESS"})
                return True
            else:
                logger.error("Failed to write configuration file.", extra={"prefix": "ERROR"})
                return False
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}", extra={"prefix": "ERROR"})
            return False
