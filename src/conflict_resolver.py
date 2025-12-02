"""
Conflict resolution module for handling patch rejections.
"""

from pathlib import Path

from .utils import get_logger, find_rejection_files
from .git_ops import GitOps

logger = get_logger(__name__)


class ConflictResolutionError(Exception):
    """Raised when conflict resolution fails."""

    pass


class ConflictResolver:
    """Handle automatic conflict resolution for patch rejections."""

    def __init__(self, repo_path: Path, git_ops: GitOps, source_commit: str):
        """Initialize conflict resolver.

        Args:
            repo_path: Path to git repository.
            git_ops: GitOps instance for git operations.
            source_commit: Source commit with original patch.
        """
        self.repo_path = repo_path
        self.git_ops = git_ops
        self.source_commit = source_commit

    def find_rejections(self) -> list[Path]:
        """Find all rejection files.

        Returns:
            List of paths to .rej files.
        """
        rejections = find_rejection_files(self.repo_path)
        logger.info(f"Found {len(rejections)} rejection files")
        return rejections

    def resolve_rejection(self, rej_file: Path) -> bool:
        """Resolve a single rejection file.

        Prints the conflict resolution prompt to the user and waits for
        manual resolution.

        Args:
            rej_file: Path to .rej file.

        Returns:
            False to indicate manual intervention is needed.
        """
        original_file = rej_file.with_suffix("")

        if not original_file.exists():
            logger.error(f"Original file not found: {original_file}")
            return False

        logger.info(f"Processing rejection: {rej_file}")

        # Build prompt for user
        prompt = self._build_resolution_prompt(
            original_file=original_file,
            rej_file=rej_file,
        )

        logger.info(f"Conflict resolution needed for: {original_file}")
        logger.debug(f"Prompt:\n{prompt}")

        # Print prompt to user
        print("\n" + "=" * 60)
        print("CONFLICT RESOLUTION REQUIRED")
        print("=" * 60)
        print(f"\n{prompt}")
        print("=" * 60 + "\n")

        return False

    def _build_resolution_prompt(self, original_file: Path, rej_file: Path) -> str:
        """Build prompt for Claude Code conflict resolution.

        Args:
            original_file: Path to original file.
            rej_file: Path to rejection file.
            rej_content: Content of rejection file.
            patch_content: Content of patch.

        Returns:
            Formatted prompt for Claude Code.
        """
        prompt = f"""I applied a patch on this codebase (Linux source code), and I found the application on file {str(original_file)} failed, which generated a rejection file {str(rej_file)}. You need to read the rejection file with the original file, and solve the conflict(s). If you need, you can also compare current file with corresponding file in commit {self.source_commit} (the ancestor commit where this patch originates) or read the entire patch file from git notes (git notes --ref=krr-patch show {self.source_commit}). Now please start to solve the conflict of file {str(original_file)}. ultrathink"""

        return prompt

    def resolve_all_rejections(self) -> dict[Path, bool]:
        """Resolve all rejection files.

        Returns:
            Dictionary mapping rejection file paths to resolution success.
        """
        rejections = self.find_rejections()

        if not rejections:
            logger.info("No rejection files found")
            return {}

        results = {}
        for rej_file in rejections:
            try:
                success = self.resolve_rejection(rej_file)
                results[rej_file] = success
            except Exception as e:
                logger.error(f"Error resolving {rej_file}: {e}")
                results[rej_file] = False

        return results

    def get_resolution_status(self) -> dict:
        """Get status of rejections and resolutions.

        Returns:
            Dictionary with resolution status.
        """
        rejections = self.find_rejections()
        return {
            "total_rejections": len(rejections),
            "rejection_files": [str(r) for r in rejections],
            "status": "NEEDS_MANUAL_VERIFICATION",
        }
