"""Base Inference Engine interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional


class BaseInferenceEngine(ABC):
    """Abstract Base Class defining the unified interface for LLM inference engines."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the inference engine with configuration settings.

        Args:
            config: Configuration dictionary.
        """
        self.config = config
        self.is_loaded = False
        self.current_model_id: Optional[str] = None

    @abstractmethod
    def load_model(self, model_path: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Loads a model into memory.

        Args:
            model_path: Absolute local path or HF repo ID of the model.
            parameters: Override parameters for model loading (e.g. quantization).
        """
        pass

    @abstractmethod
    def unload_model(self) -> None:
        """Unloads the current model and releases GPU/system resources."""
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        generation_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Generates tokens streamingly.

        Args:
            prompt: The input prompt.
            generation_params: Generation hyper-parameters (temperature, top_p, etc.).

        Yields:
            str: The generated token string.
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Retrieves engine stats and memory usage.

        Returns:
            Dict[str, Any]: Engine status metadata.
        """
        pass

    @abstractmethod
    def is_compatible(self, model_path: str) -> bool:
        """Checks if the engine is compatible with a given model format.

        Args:
            model_path: Path or identifier of the model.

        Returns:
            bool: True if compatible.
        """
        pass
