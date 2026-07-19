"""Environment detection utilities."""

import sys
from typing import Literal

EnvironmentType = Literal["colab", "jupyter", "terminal"]


def detect_environment() -> EnvironmentType:
    """Detects the current runtime environment.

    Returns:
        EnvironmentType: 'colab' if running inside Google Colab,
                         'jupyter' if running in standard Jupyter/IPython,
                         'terminal' otherwise.
    """
    # Check if 'google.colab' module is in sys.modules (classic Colab check)
    if "google.colab" in sys.modules:
        return "colab"

    # Alternatively, check if ipython is running
    try:
        from IPython import get_ipython

        ipy = get_ipython()
        if ipy is not None:
            # Check if it has 'google.colab' in its type or attributes
            if "google.colab" in type(ipy).__module__:
                return "colab"
            return "jupyter"
    except ImportError:
        pass

    return "terminal"


def is_colab() -> bool:
    """Helper to check if running in Google Colab.

    Returns:
        bool: True if in Colab, False otherwise.
    """
    return detect_environment() == "colab"
