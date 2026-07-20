"""Logging module for APEX with safe handlers and semantic UI formatting."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

# Optional color support
try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


class ColoredFormatter(logging.Formatter):
    """Custom Formatter that adds colors to logs if supported (for standard terminal)."""

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


class SemanticLogFormatter(logging.Formatter):
    """HTML-based formatter for the Colab Runtime Console."""

    COLORS = {
        "INFO": "color: #aaaaaa;",            # Gray
        "SUCCESS": "color: #28a745;",         # Green
        "WARNING": "color: #ffc107;",         # Yellow
        "ERROR": "color: #dc3545;",           # Red
        "DOWNLOAD": "color: #0d6efd;",        # Blue
        "GPU": "color: #6f42c1;",             # Purple
        "API": "color: #0dcaf0;",             # Cyan
        "MODEL": "color: #fd7e14;",           # Orange
        "WORKER": "color: #20c997;",          # Light Blue
        "SYSTEM": "color: #6c757d;"           # Dark Gray
    }

    def format(self, record: logging.LogRecord) -> str:
        # Check for a specific prefix, fallback to levelname (INFO, ERROR, etc.)
        prefix = getattr(record, "prefix", record.levelname)
        if prefix == "INFO" and record.levelname == "ERROR":
            prefix = "ERROR"
            
        color_style = self.COLORS.get(prefix.upper(), "color: #d4d4d4;")
        
        # HTML formatting for the output widget
        timestamp = self.formatTime(record, "%H:%M:%S")
        message = record.getMessage()
        
        return f'<span style="color: #888888;">[{timestamp}]</span> <span style="{color_style} font-weight: bold; width: 80px; display: inline-block;">{prefix.upper()}</span> {message}'


class WidgetLogHandler(logging.Handler):
    """Intercepts logs and appends them as HTML to an ipywidgets.Output."""
    
    def __init__(self):
        super().__init__()
        self.widget: Optional[Any] = None
        self.setFormatter(SemanticLogFormatter())

    def set_widget(self, widget: Any):
        """Bind the UI Output widget to this handler."""
        self.widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        if self.widget:
            try:
                # We expect the widget to be an ipywidgets.Output
                msg = self.format(record)
                from IPython.display import HTML
                self.widget.append_display_data(HTML(f"<div>{msg}</div>"))
            except Exception:
                pass


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

    def flush(self) -> None:
        if self.is_broken:
            return
        try:
            super().flush()
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

    def flush(self) -> None:
        if self.is_broken:
            return
        try:
            super().flush()
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


# Global widget handler instance so dashboard can attach to it easily
_global_widget_handler = WidgetLogHandler()

def get_widget_handler() -> WidgetLogHandler:
    return _global_widget_handler


def remove_stream_handlers(logger: logging.Logger) -> None:
    """NO-OP in V1. We want standard streaming output in notebook cells."""
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

    # 1. Console Handler using SafeStreamHandler + DynamicStreamProxy
    console_handler = SafeStreamHandler(DynamicStreamProxy())
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)
    
    # 2. Widget Log Handler for the Dashboard
    logger.addHandler(get_widget_handler())

    # 3. File Handler (if log_file path provided)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = SafeFileHandler(str(log_file), encoding="utf-8")
            file_fmt = "[%(asctime)s] [%(levelname)s] (%(name)s) %(filename)s:%(lineno)d: %(message)s"
            file_formatter = logging.Formatter(file_fmt, datefmt="%Y-%m-%d %H:%M:%S")
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except OSError:
            pass

    return logger
