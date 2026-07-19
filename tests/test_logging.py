"""Unit tests for logging system."""

import logging
from pathlib import Path
from runtime.logging.logger import setup_logger


def test_logger_setup(tmp_path: Path):
    """Tests that logger initializes properly and writes to file."""
    log_file = tmp_path / "test.log"
    logger = setup_logger(name="test_logger", log_file=log_file, level=logging.DEBUG)

    assert isinstance(logger, logging.Logger)
    assert len(logger.handlers) >= 1

    test_msg = "Diagnostic test message"
    logger.info(test_msg)

    # Force flush handlers
    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert test_msg in content
    assert "[INFO]" in content
