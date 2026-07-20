"""Logging module for APEX with safe, resilient handlers."""

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


class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that disables itself if the underlying stream is disconnected (Colab safe)."""
    
    def __init__(self, stream=None):
        super().__init__(stream)
        self.is_broken = False

    def emit(self, record: logging.LogRecord) -> None:
        if self.is_broken:
            return
        try:
            super().emit(record)
        except OSError:
            self.is_broken = True
        except Exception:
            self.is_broken = True


class SafeFileHandler(logging.FileHandler):
    """A FileHandler that disables itself if the underlying file system disconnects (Drive safe)."""
    
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        super().__init__(filename, mode, encoding, delay)
        self.is_broken = False

    def emit(self, record: logging.LogRecord) -> None:
        if self.is_broken:
            return
        try:
            super().emit(record)
        except OSError:
            self.is_broken = True
        except Exception:
            self.is_broken = True


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
    """Configures and retrieves the logger with resilient handlers.

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

    # Console Handler using SafeStreamHandler + DynamicStreamProxy
    console_handler = SafeStreamHandler(DynamicStreamProxy())
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)


    # File Handler (if log_file path provided)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = SafeFileHandler(str(log_file), encoding="utf-8")
            file_fmt = "[%(asctime)s] [%(levelname)s] (%(name)s) %(filename)s:%(lineno)d: %(message)s"
            file_formatter = logging.Formatter(file_fmt, datefmt="%Y-%m-%d %H:%M:%S")
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except OSError as e:
            # We don't bubble this up or log recursively, just skip file logging.
            pass

    return logger
