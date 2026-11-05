"""Logging module for APEX with safe handlers and semantic UI formatting."""

import collections
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, List, Optional

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


# ── Secret Redaction & Live Observability Buffer ──────────────────────────────

REDACTION_PATTERNS = [
    # Hugging Face access tokens (hf_...)
    (re.compile(r"hf_[a-zA-Z0-9]{20,}", re.IGNORECASE), "hf_●●●●[REDACTED]"),
    # Bearer tokens in Authorization headers
    (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{10,})", re.IGNORECASE), "Bearer ●●●●[REDACTED]"),
    # Explicit keys / secrets in key=val / JSON formats
    (
        re.compile(r"((?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-\.]{8,})(['\"]?)", re.IGNORECASE),
        r"\1●●●●[REDACTED]\3",
    ),
    # Cloudflare tunnel tokens
    (
        re.compile(r"(tunnel[_-]?token\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{20,})(['\"]?)", re.IGNORECASE),
        r"\1●●●●[REDACTED]\3",
    ),
]


def redact_sensitive_data(text: str) -> str:
    """Redacts sensitive API keys, Hugging Face tokens, and credentials from log strings."""
    if not text:
        return ""
    result = str(text)
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


@dataclass
class LogEntry:
    """Structured representation of an in-memory log event for the Developer Console."""
    timestamp: str          # "HH:MM:SS"
    level: str              # "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    logger_name: str        # e.g. "runtime.lifecycle"
    message: str            # Redacted message content
    raw_time: float = field(default_factory=time.time)

    def to_formatted_string(self) -> str:
        return f"[{self.timestamp}] {self.level:<7} [{self.logger_name}] {self.message}"


class LogBufferHandler(logging.Handler):
    """Scoped in-memory log buffer that captures, redacts, and broadcasts live telemetry."""

    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.capacity = capacity
        self.buffer: Deque[str] = collections.deque(maxlen=capacity)
        self.entries: Deque[LogEntry] = collections.deque(maxlen=capacity)
        self.listeners: List[Callable[[LogEntry], None]] = []
        self.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)-7s [%(name)s] %(message)s", datefmt="%H:%M:%S")
        )

    def add_listener(self, callback: Callable[[LogEntry], None]) -> None:
        """Subscribes a UI or progress callback to receive live log entries."""
        if callback not in self.listeners:
            self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]) -> None:
        """Unsubscribes a listener."""
        if callback in self.listeners:
            self.listeners.remove(callback)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            raw_msg = record.getMessage()
            clean_msg = redact_sensitive_data(raw_msg)

            ts = time.strftime("%H:%M:%S", time.localtime(record.created))
            entry = LogEntry(
                timestamp=ts,
                level=record.levelname,
                logger_name=record.name,
                message=clean_msg,
                raw_time=record.created,
            )
            self.entries.append(entry)

            formatted = f"[{ts}] {record.levelname:<7} [{record.name}] {clean_msg}"
            self.buffer.append(formatted)

            for listener in list(self.listeners):
                try:
                    listener(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    def get_logs(self, max_lines: int = 200) -> str:
        """Returns the most recent formatted log lines (for legacy callers)."""
        lines = list(self.buffer)[-max_lines:]
        return "\n".join(lines) if lines else "No runtime logs recorded yet."

    def get_entries(
        self,
        level_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        max_lines: int = 500,
        *,
        level: Optional[str] = None,
        query: Optional[str] = None,
        max_entries: Optional[int] = None,
    ) -> List[LogEntry]:
        """Returns filtered LogEntry items based on level and search term."""
        effective_level = level if level is not None else level_filter
        effective_query = query if query is not None else search_query
        effective_max = max_entries if max_entries is not None else max_lines

        items = list(self.entries)
        if effective_level and effective_level.upper() not in ("ALL", ""):
            items = [e for e in items if e.level.upper() == effective_level.upper()]
        if effective_query and effective_query.strip():
            sq = effective_query.strip().lower()
            items = [e for e in items if sq in e.message.lower() or sq in e.logger_name.lower()]
        return items[-effective_max:]

    def clear(self) -> None:
        """Clears both log buffers."""
        self.buffer.clear()
        self.entries.clear()


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
    """Removes standard console/stdout StreamHandlers from logger, leaving memory/widget handlers intact."""
    for handler in list(logger.handlers):
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, (WidgetLogHandler,)):
            if handler.__class__.__name__ == "LogBufferHandler":
                continue
            logger.removeHandler(handler)


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
