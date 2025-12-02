"""
Commit file management module for reading and parsing commit lists.
"""

import sys
from pathlib import Path
from typing import List

from .utils import get_logger

logger = get_logger(__name__)


class CommitManagerError(Exception):
    """Raised when commit manager operations fail."""

    pass


class CommitManager:
    """Manage commit lists from files."""

    def __init__(self, commit_file: Path):
        """Initialize commit manager.

        Args:
            commit_file: Path to file containing commit hashes.

        Raises:
            CommitManagerError: If file doesn't exist or is empty.
        """
        self.commit_file = Path(commit_file)
        self.commits = self._read_commits()
        logger.info(f"Loaded {len(self.commits)} commits from {self.commit_file}")

    def _read_commits(self) -> List[str]:
        """Read commit hashes from file.

        Returns:
            List of commit hashes.

        Raises:
            CommitManagerError: If file doesn't exist or cannot be read.
        """
        try:
            if not self.commit_file.exists():
                raise CommitManagerError(
                    f"Commit file not found: {self.commit_file}"
                )

            with open(self.commit_file, 'r') as f:
                commits = [line.strip() for line in f if line.strip()]

            if not commits:
                raise CommitManagerError(
                    f"No commits found in file: {self.commit_file}"
                )

            return commits

        except FileNotFoundError as e:
            raise CommitManagerError(f"Cannot read commit file: {e}") from e
        except Exception as e:
            raise CommitManagerError(
                f"Error reading commit file: {e}"
            ) from e

    def find_commit_index(self, commit: str) -> int:
        """Find the index of a commit in the list.

        Args:
            commit: Commit hash to find.

        Returns:
            Index of the commit.

        Raises:
            CommitManagerError: If commit not found.
        """
        try:
            return self.commits.index(commit)
        except ValueError as e:
            raise CommitManagerError(
                f"Commit '{commit}' not found in {self.commit_file}"
            ) from e

    def get_previous_commit(self, commit: str) -> str:
        """Get the previous commit in the sequence.

        Args:
            commit: The commit to get predecessor for (commit B).

        Returns:
            The previous commit (commit A).

        Raises:
            CommitManagerError: If commit is first in list or not found.
        """
        index = self.find_commit_index(commit)

        if index == 0:
            raise CommitManagerError(
                f"Commit '{commit}' is the first commit in the file. "
                "No previous commit available."
            )

        return self.commits[index - 1]

    def get_next_commit(self, commit: str) -> str:
        """Get the next commit in the sequence.

        Args:
            commit: The commit to get successor for.

        Returns:
            The next commit.

        Raises:
            CommitManagerError: If commit is last in list or not found.
        """
        index = self.find_commit_index(commit)

        if index == len(self.commits) - 1:
            raise CommitManagerError(
                f"Commit '{commit}' is the last commit in the file. "
                "No next commit available."
            )

        return self.commits[index + 1]

    def get_all_commits(self) -> List[str]:
        """Get all commits in the sequence.

        Returns:
            List of all commits.
        """
        return self.commits.copy()

    def get_commit_position(self, commit: str) -> tuple[int, int]:
        """Get the position and total count for a commit.

        Args:
            commit: Commit to get position for.

        Returns:
            Tuple of (current_position, total_count).

        Raises:
            CommitManagerError: If commit not found.
        """
        index = self.find_commit_index(commit)
        return index + 1, len(self.commits)
