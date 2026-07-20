"""UI Module Registry for dynamic and fault-tolerant loading of interface components."""

import importlib
import logging
from typing import Any, Dict, List

logger = logging.getLogger("runtime.ui.registry")


class UIRegistry:
    """Dynamically registers and loads UI modules, skipping missing ones without crashing."""

    def __init__(self):
        """Initializes the UI Registry."""
        self._registered_modules: Dict[str, str] = {}
        self._loaded_modules: Dict[str, Any] = {}

    def register(self, name: str, module_path: str) -> None:
        """Registers a UI module path by a friendly name.

        Args:
            name: Friendly name (e.g., 'dashboard', 'benchmarks')
            module_path: Python import path (e.g., 'runtime.ui.dashboard')
        """
        self._registered_modules[name] = module_path

    def load_all(self) -> None:
        """Attempts to load all registered UI modules."""
        for name, path in self._registered_modules.items():
            self.load(name)

    def load(self, name: str) -> Any:
        """Dynamically imports a single registered module by name.

        Args:
            name: Friendly name of the module.

        Returns:
            Any: The loaded module, or None if it fails.
        """
        if name not in self._registered_modules:
            logger.warning(f"UI module '{name}' is not registered.")
            return None

        if name in self._loaded_modules:
            return self._loaded_modules[name]

        module_path = self._registered_modules[name]
        try:
            module = importlib.import_module(module_path)
            self._loaded_modules[name] = module
            return module
        except ModuleNotFoundError as e:
            logger.warning(f"UI module '{name}' not found at '{module_path}'. Skipping... ({e})")
            return None
        except Exception as e:
            logger.error(f"Error loading UI module '{name}': {e}")
            return None

    def get_module(self, name: str) -> Any:
        """Gets a loaded module, or attempts to load it if not loaded.

        Args:
            name: Friendly name of the module.

        Returns:
            Any: The loaded module, or None.
        """
        if name in self._loaded_modules:
            return self._loaded_modules[name]
        return self.load(name)

    def list_available(self) -> List[str]:
        """Lists successfully loaded UI modules."""
        return list(self._loaded_modules.keys())

    def validate_consistency(self) -> Dict[str, List[str]]:
        """Validates the state of registered vs loaded modules.

        Returns:
            Dict[str, List[str]]: Report containing 'missing' and 'loaded' lists.
        """
        missing = [name for name in self._registered_modules if name not in self._loaded_modules]
        loaded = list(self._loaded_modules.keys())
        return {"missing": missing, "loaded": loaded}
