"""Logging module for APEX."""


import logging
import sys
from pathlib import Path
from typing import Optional

# Optional color support
try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


class ColoredFormatter(logging.Formatter):
    """Custom Formatter that adds colors to logs if supported."""

    COLORS = {
        logging.DEBUG: Fore.CYAN if HAS_COLOR else "",
        logging.INFO: Fore.GREEN if HAS_COLOR else "",
        logging.WARNING: Fore.YELLOW if HAS_COLOR else "",
        logging.ERROR: Fore.RED if HAS_COLOR else "",
        logging.CRITICAL: Fore.RED + Style.BRIGHT if HAS_COLOR else "",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if HAS_COLOR and color else ""

        # Format timestamp, level name, and message
        log_fmt = f"{color}[%(asctime)s] [%(levelname)s] (%(name)s) %(message)s{reset}"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class DynamicStreamProxy:
    """Wrapper that always resolves to the active sys.stdout stream in Colab."""
    def write(self, data: str) -> int:
        try:
            sys.stdout.write(data)
            return len(data)
        except OSError:
            return 0

    def flush(self) -> None:
        try:
            sys.stdout.flush()
        except OSError:
            pass


def setup_logger(
    name: str = "runtime",
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configures and retrieves the logger.

    Args:
        name: Name of the logger.
        log_file: Path to the log file.
        level: Logger level.

    Returns:
        logging.Logger: The configured Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    # Console Handler using DynamicStreamProxy
    console_handler = logging.StreamHandler(DynamicStreamProxy())
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)


    # File Handler (if log_file path provided)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_fmt = "[%(asctime)s] [%(levelname)s] (%(name)s) %(filename)s:%(lineno)d: %(message)s"
            file_formatter = logging.Formatter(file_fmt, datefmt="%Y-%m-%d %H:%M:%S")
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except OSError as e:
            logger.warning(f"Could not create file log handler: {e}")

    return logger
