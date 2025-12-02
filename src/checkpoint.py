"""
Checkpoint management for workflow resumption capability.

This module provides functionality to save and restore workflow state,
allowing processes to resume from the point of failure.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from .utils import get_logger

logger = get_logger(__name__)


class Checkpoint:
    """Manage workflow checkpoints for resumption."""

    CHECKPOINT_FILE = ".workflow_checkpoint.json"

    def __init__(self, repo_path: Path):
        """Initialize checkpoint manager.

        Args:
            repo_path: Path to git repository.
        """
        self.repo_path = repo_path
        self.checkpoint_path = repo_path / self.CHECKPOINT_FILE

    def save(
        self,
        source_commit: str,
        base_commit: str,
        last_completed_step: int,
        step_name: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Save workflow checkpoint.

        Args:
            source_commit: Source commit hash.
            base_commit: Base commit hash.
            last_completed_step: Number of last completed step.
            step_name: Name of last completed step.
            metadata: Additional metadata to save.
        """
        checkpoint_data = {
            "source_commit": source_commit,
            "base_commit": base_commit,
            "last_completed_step": last_completed_step,
            "last_completed_step_name": step_name,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        with open(self.checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info(f"Checkpoint saved: step {last_completed_step} ({step_name})")

    def load(self) -> Optional[dict]:
        """Load workflow checkpoint.

        Returns:
            Checkpoint data dict, or None if no checkpoint exists.
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            with open(self.checkpoint_path, "r") as f:
                data = json.load(f)
            logger.info(
                f"Checkpoint loaded: step {data['last_completed_step']} "
                f"({data['last_completed_step_name']})"
            )
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None

    def exists(self) -> bool:
        """Check if checkpoint exists.

        Returns:
            True if checkpoint file exists, False otherwise.
        """
        return self.checkpoint_path.exists()

    def clear(self) -> None:
        """Clear the checkpoint file after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.info("Checkpoint cleared after successful workflow completion")

    def get_next_step(self, checkpoint_data: dict) -> int:
        """Get the next step to execute based on checkpoint.

        Args:
            checkpoint_data: Loaded checkpoint data.

        Returns:
            Step number to resume from (1-indexed).
        """
        # Return the next step after the last completed one
        return checkpoint_data["last_completed_step"] + 1

    def validate_checkpoint(
        self, checkpoint_data: dict, source_commit: str, base_commit: str
    ) -> bool:
        """Validate that checkpoint matches current parameters.

        Args:
            checkpoint_data: Loaded checkpoint data.
            source_commit: Current source commit.
            base_commit: Current base commit.

        Returns:
            True if checkpoint is valid for current parameters.
        """
        return (
            checkpoint_data.get("source_commit") == source_commit
            and checkpoint_data.get("base_commit") == base_commit
        )
