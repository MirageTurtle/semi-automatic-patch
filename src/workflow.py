"""
Workflow orchestration module for patch application.
"""

import sys
from pathlib import Path

from .config import Config
from .utils import get_logger
from .git_ops import GitOps, GitOperationError
from .conflict_resolver import ConflictResolver
from .checkpoint import Checkpoint

logger = get_logger(__name__)


class WorkflowError(Exception):
    """Raised when workflow execution fails."""

    pass


class PatchApplicationWorkflow:
    """Orchestrate the patch application workflow."""

    def __init__(self, config: Config):
        """Initialize workflow.

        Args:
            config: Configuration for the workflow.
        """
        self.config = config
        self.git = GitOps(config.repo_path, config.notes_ref)
        self.checkpoint = Checkpoint(config.repo_path)

    def execute(
        self, source_commit: str, base_commit: str, skip_resolution: bool = False, resume: bool = False
    ) -> int:
        """Execute the patch application workflow.

        Follows the steps defined in PLAN.md:
        1. Checkout base commit
        2. Apply patch from git notes
        3. Find rejection files
        4. Resolve conflicts (if not skipped)
        5. Stage changes
        6. Create git note
        7. Verify git note
        8. Clean working directory

        Args:
            source_commit: Source commit with patch (commit A).
            base_commit: Base commit to apply patch to (commit B).
            skip_resolution: Skip automatic conflict resolution.
            resume: Resume from last checkpoint if it exists.

        Returns:
            Exit code (0 for success, non-zero for failure).
        """
        try:
            logger.info("=" * 60)
            logger.info("Starting patch application workflow")
            logger.info("=" * 60)

            # Determine starting step
            start_step = 1
            checkpoint_data = None

            if resume and self.checkpoint.exists():
                checkpoint_data = self.checkpoint.load()
                if checkpoint_data and self.checkpoint.validate_checkpoint(
                    checkpoint_data, source_commit, base_commit
                ):
                    start_step = self.checkpoint.get_next_step(checkpoint_data)
                    logger.info(f"Resuming from step {start_step}")
                    print(f"\nResuming workflow from step {start_step}\n")
                else:
                    logger.warning("Checkpoint validation failed, starting from beginning")
                    start_step = 1
            elif self.checkpoint.exists():
                logger.warning("Existing checkpoint found but resume not requested")
                print("\nWarning: Existing checkpoint found.")
                print("Run with --resume to continue from where it failed,")
                print("or remove .workflow_checkpoint.json to start fresh.\n")
                return 1

            # Step 1: Ensure working directory is clean (only on fresh start)
            if start_step <= 1:
                logger.info("Step 1: Checking working directory")
                self.git.ensure_clean_working_dir()
                self.checkpoint.save(source_commit, base_commit, 1, "working directory check")

            # Step 2: Checkout base commit (only if not resumed past it)
            if start_step <= 2:
                logger.info(f"Step 2: Checking out base commit {base_commit}")
                self.git.checkout(base_commit)
                self.checkpoint.save(source_commit, base_commit, 2, "checkout base commit")

            # Step 3: Get and apply patch from git notes
            if start_step <= 3:
                logger.info(f"Step 3: Retrieving patch from git notes ({source_commit})")
                patch_content = self.git.get_git_note(source_commit)

                if not patch_content:
                    raise WorkflowError(
                        f"No git note found for commit {source_commit}. "
                        "Cannot proceed without patch."
                    )

                logger.info("Applying patch with rejection handling")
                success, output = self.git.apply_patch(patch_content)

                if output:
                    logger.debug(f"Patch application output:\n{output}")

                self.checkpoint.save(source_commit, base_commit, 3, "apply patch")

            # Step 4: Find and resolve rejections
            if start_step <= 4:
                logger.info("Step 4: Finding rejection files")
                resolver = ConflictResolver(self.config.repo_path, self.git, source_commit)
                rejections = resolver.find_rejections()

                if rejections:
                    logger.warning(f"Found {len(rejections)} rejection files")
                    for rej in rejections:
                        logger.warning(f"  - {rej.relative_to(self.config.repo_path)}")

                    if not skip_resolution:
                        logger.info("Step 5: Displaying conflict resolution prompts")
                        resolver.resolve_all_rejections()

                        logger.warning(
                            f"Manual conflict resolution required for {len(rejections)} file(s)"
                        )
                        print("\n" + "=" * 60)
                        print("MANUAL RESOLUTION REQUIRED")
                        print("=" * 60)
                        print(f"\nPlease resolve the following rejection files:")
                        for rej_file in rejections:
                            print(f"  - {rej_file.relative_to(self.config.repo_path)}")
                        print("\nAfter resolving all conflicts:")
                        print("  1. Review all changes")
                        print("  2. Test the patched code")
                        print("  3. Run: git add -A")
                        print("  4. Run: python main.py apply {} {} --resume".format(source_commit, base_commit))
                        print("=" * 60 + "\n")
                        # Save checkpoint at conflict resolution point
                        self.checkpoint.save(source_commit, base_commit, 4, "conflict resolution pending")
                        return 0
                    else:
                        logger.info("Skipping automatic conflict resolution")
                else:
                    logger.info("No rejection files found - patch applied cleanly")

                self.checkpoint.save(source_commit, base_commit, 4, "find rejections")

            # Step 6: Stage changes
            if start_step <= 5:
                logger.info("Step 6: Staging all changes")
                self.git.stage_changes()
                self.checkpoint.save(source_commit, base_commit, 5, "stage changes")

            # Step 7: Create git note
            if start_step <= 6:
                logger.info("Step 7: Creating git note")
                self.git.create_git_note(base_commit)
                self.checkpoint.save(source_commit, base_commit, 6, "create git note")

            # Step 8: Verify git note
            if start_step <= 7:
                logger.info("Step 8: Verifying git note")
                note_content = self.git.verify_git_note(base_commit)
                logger.info(f"Git note created successfully ({len(note_content)} bytes)")
                self.checkpoint.save(source_commit, base_commit, 7, "verify git note")

            # Step 9: Clean working directory
            if start_step <= 8:
                logger.info("Step 9: Cleaning working directory")
                self.git.reset_hard()
                self.git.clean_untracked()

            # Clear checkpoint on success
            self.checkpoint.clear()

            logger.info("=" * 60)
            logger.info("Workflow completed successfully")
            logger.info("=" * 60)
            return 0

        except GitOperationError as e:
            logger.error(f"Git operation failed: {e}")
            # Checkpoint is already saved, don't clean up
            return 1
        except WorkflowError as e:
            logger.error(f"Workflow error: {e}")
            # Checkpoint is already saved, don't clean up
            return 1
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            # Checkpoint is already saved, don't clean up
            return 1

    def show_git_note(self, commit: str) -> str:
        """Show git note for a commit.

        Args:
            commit: Commit hash or reference.

        Returns:
            Note content.

        Raises:
            WorkflowError: If note doesn't exist.
        """
        try:
            note = self.git.get_git_note(commit)
            if not note:
                raise WorkflowError(f"No git note found for {commit}")
            return note
        except GitOperationError as e:
            raise WorkflowError(str(e)) from e

    def create_git_note(self, commit: str = "HEAD") -> None:
        """Create git note from current changes.

        Args:
            commit: Commit to attach note to.

        Raises:
            WorkflowError: If note creation fails.
        """
        try:
            logger.info(f"Creating git note for {commit}")
            self.git.create_git_note(commit)
            logger.info("Git note created successfully")
        except GitOperationError as e:
            raise WorkflowError(str(e)) from e
