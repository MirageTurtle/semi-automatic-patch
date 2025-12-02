"""
Utility functions for patch application workflow.
"""

import logging
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration.

    Args:
        verbose: Enable verbose logging.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def find_rejection_files(root_path: Path) -> list[Path]:
    """Find all rejection files in repository.

    Args:
        root_path: Root path to search from.

    Returns:
        List of paths to .rej files.
    """
    return sorted(root_path.rglob("*.rej"))


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
