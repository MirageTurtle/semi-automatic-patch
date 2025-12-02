"""
Configuration module for patch application workflow.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Configuration for patch application workflow."""

    repo_path: Path
    notes_ref: str = "krr-patch"
    claude_model: str = "claude-opus"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")
