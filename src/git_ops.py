"""
Git operations module for patch application workflow.
"""

import subprocess
from pathlib import Path
from typing import Optional

from .utils import get_logger

logger = get_logger(__name__)


class GitOperationError(Exception):
    """Raised when a git operation fails."""

    pass


class GitOps:
    """Handle git operations for patch application."""

    def __init__(self, repo_path: Path, notes_ref: str = "krr-patch"):
        """Initialize git operations handler.

        Args:
            repo_path: Path to git repository.
            notes_ref: Git notes reference name.

        Raises:
            GitOperationError: If repo is not a valid git repository.
        """
        self.repo_path = repo_path
        self.notes_ref = notes_ref

        # Verify repository exists
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            raise GitOperationError(f"Not a git repository: {repo_path}")

    def _run_git(self, *args, cwd: Optional[Path] = None, check: bool = True) -> str:
        """Run a git command and return output.

        Args:
            args: Git command arguments (after 'git').
            cwd: Working directory for command.
            check: Raise on non-zero exit code.

        Returns:
            Command output (stdout).

        Raises:
            GitOperationError: If command fails and check=True.
        """
        cwd = cwd or self.repo_path
        cmd = ["git"] + list(args)

        try:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, check=check
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"Git command failed: {' '.join(cmd)}\n{e.stderr}"
            logger.error(error_msg)
            if check:
                raise GitOperationError(error_msg) from e
            return ""

    def checkout(self, commit: str) -> None:
        """Checkout a specific commit.

        Args:
            commit: Commit hash or reference.

        Raises:
            GitOperationError: If checkout fails.
        """
        logger.info(f"Checking out commit: {commit}")
        self._run_git("checkout", commit)

    def is_working_dir_clean(self) -> bool:
        """Check if working directory is clean.

        Returns:
            True if working directory is clean, False otherwise.
        """
        status = self._run_git("status", "--porcelain")
        return len(status) == 0

    def ensure_clean_working_dir(self) -> None:
        """Ensure working directory is clean.

        Raises:
            GitOperationError: If working directory is not clean.
        """
        if not self.is_working_dir_clean():
            raise GitOperationError(
                "Working directory is not clean. Please commit or stash changes."
            )

    def get_git_note(self, commit: str) -> str:
        """Get git note for a commit.

        Args:
            commit: Commit hash or reference.

        Returns:
            Note content, or empty string if no note exists.

        Raises:
            GitOperationError: If commit doesn't exist.
        """
        logger.info(f"Reading git note from {commit}")
        try:
            note = self._run_git("notes", f"--ref={self.notes_ref}", "show", commit)
            return note
        except GitOperationError as e:
            if "No note found" in str(e) or "ref/notes" in str(e):
                logger.warning(f"No git note found for {commit}")
                return ""
            raise

    def apply_patch(self, patch_content: str) -> tuple[bool, str]:
        """Apply a patch with rejection handling.

        Args:
            patch_content: Patch content as string.

        Returns:
            Tuple of (success, output).
        """
        logger.info("Applying patch with rejection handling")
        try:
            result = subprocess.run(
                ["git", "apply", "--reject"],
                input=patch_content,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            # git apply --reject returns non-zero if there are rejections
            # but doesn't fail completely
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            raise GitOperationError(f"Failed to apply patch: {e}") from e

    def stage_changes(self) -> None:
        """Stage all changes in working directory.

        Raises:
            GitOperationError: If staging fails.
        """
        logger.info("Staging all changes")
        self._run_git("add", "-A")

    def create_git_note(self, commit: str) -> str:
        """Create a git note from current changes.

        Args:
            commit: Commit to attach note to (defaults to HEAD).

        Returns:
            The note content.

        Raises:
            GitOperationError: If note creation fails.
        """
        logger.info(f"Creating git note for {commit}")

        # Get the diff
        diff = self._run_git("diff", "HEAD")

        if not diff:
            logger.warning("No changes to create note from")
            return ""

        # Create the note
        self._run_git(
            "notes",
            f"--ref={self.notes_ref}",
            "add",
            "-f",
            "-F",
            "-",
            commit,
            input=diff,
        )

        # In reality, we need to pipe the diff, so let's use a subprocess approach
        try:
            # Get diff
            diff_result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Create note
            note_cmd = [
                "git",
                "notes",
                f"--ref={self.notes_ref}",
                "add",
                "-f",
                "-F",
                "-",
                commit,
            ]
            subprocess.run(
                note_cmd,
                input=diff_result.stdout,
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )

            return diff_result.stdout
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to create git note: {e}") from e

    def verify_git_note(self, commit: str) -> str:
        """Verify git note exists and return its content.

        Args:
            commit: Commit to verify note for.

        Returns:
            Note content.

        Raises:
            GitOperationError: If note doesn't exist.
        """
        logger.info(f"Verifying git note for {commit}")
        note = self.get_git_note(commit)
        if not note:
            raise GitOperationError(f"Git note not found for {commit}")
        return note

    def reset_hard(self) -> None:
        """Hard reset working directory to HEAD.

        Raises:
            GitOperationError: If reset fails.
        """
        logger.info("Hard resetting working directory")
        self._run_git("reset", "--hard", "HEAD")

    def clean_untracked(self) -> None:
        """Remove untracked files and directories.

        Raises:
            GitOperationError: If clean fails.
        """
        logger.info("Cleaning untracked files and directories")
        self._run_git("clean", "-fdx")

    def get_commit_hash(self, ref: str = "HEAD") -> str:
        """Get the full commit hash for a reference.

        Args:
            ref: Commit reference (default: HEAD).

        Returns:
            Full commit hash.

        Raises:
            GitOperationError: If reference doesn't exist.
        """
        hash_val = self._run_git("rev-parse", ref)
        return hash_val
