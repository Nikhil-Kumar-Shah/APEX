"""UI and dashboard presentation package."""

from runtime.ui.registry import UIRegistry

# Initialize global UI registry
ui_registry = UIRegistry()

# Register core UI modules dynamically
ui_registry.register("dashboard", "runtime.ui.dashboard")
ui_registry.register("docs_center", "runtime.ui.docs_center")
ui_registry.register("benchmarks", "runtime.ui.benchmarks")
ui_registry.register("logs", "runtime.ui.logs")
ui_registry.register("updater", "runtime.ui.updater")

__all__ = [
    "ui_registry",
    "UIRegistry",
]
