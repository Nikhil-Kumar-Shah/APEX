"""UI and dashboard presentation package."""

from runtime.ui.registry import UIRegistry
from runtime.ui.dashboard import RuntimeDashboard
from runtime.ui.config_ui import ConfigUI
from runtime.ui.chat_ui import ChatUI
from runtime.ui.launcher import APEXLauncher

# Initialize global UI registry
ui_registry = UIRegistry()

# Register core UI modules dynamically
ui_registry.register("launcher", "runtime.ui.launcher")
ui_registry.register("config_ui", "runtime.ui.config_ui")
ui_registry.register("chat_ui", "runtime.ui.chat_ui")
ui_registry.register("dashboard", "runtime.ui.dashboard")
ui_registry.register("docs_center", "runtime.ui.docs_center")
ui_registry.register("benchmarks", "runtime.ui.benchmarks")
ui_registry.register("logs", "runtime.ui.logs")
ui_registry.register("updater", "runtime.ui.updater")

__all__ = [
    "ui_registry",
    "UIRegistry",
    "RuntimeDashboard",
    "ConfigUI",
    "ChatUI",
    "APEXLauncher",
]
