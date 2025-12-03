"""
Workflow orchestration module for patch application.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .config import Config
from .utils import get_logger
from .git_ops import GitOps, GitOperationError
from .conflict_resolver import ConflictResolver
from .checkpoint import Checkpoint

logger = get_logger(__name__)


class WorkflowError(Exception):
    """Raised when workflow execution fails."""

    pass


@dataclass
class TrialResult:
    """Result of a patch application trial."""

    source_commit: str
    base_commit: str
    success: bool
    rejection_count: int
    rejection_files: List[Path]
    error_message: Optional[str] = None


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

    def trial_patch_application(
        self, source_commit: str, base_commit: str
    ) -> TrialResult:
        """Trial patch application without completing workflow.

        Tests if a patch from source_commit can be applied to base_commit.
        Counts rejection files but does not perform conflict resolution.
        Leaves the patch applied in the working directory (caller must clean up if needed).

        Args:
            source_commit: Source commit with patch.
            base_commit: Base commit to apply patch to.

        Returns:
            TrialResult with success status and rejection count.
        """
        try:
            logger.debug(f"Trialing patch from {source_commit} to {base_commit}")

            # Step 1: Ensure working directory is clean
            logger.debug("Validating clean working directory")
            self.git.ensure_clean_working_dir()

            # Step 2: Checkout base commit
            logger.debug(f"Checking out base commit {base_commit}")
            self.git.checkout(base_commit)

            # Step 3: Get and apply patch
            logger.debug(f"Retrieving patch from git notes ({source_commit})")
            patch_content = self.git.get_git_note(source_commit)

            if not patch_content:
                logger.debug(f"No git note found for {source_commit}")
                return TrialResult(
                    source_commit=source_commit,
                    base_commit=base_commit,
                    success=False,
                    rejection_count=-1,
                    rejection_files=[],
                    error_message=f"No git note found for {source_commit}",
                )

            logger.debug("Applying patch with rejection handling")
            success, output = self.git.apply_patch(patch_content)

            if output:
                logger.debug(f"Patch application output:\n{output}")

            # Step 4: Find rejection files
            logger.debug("Finding rejection files")
            resolver = ConflictResolver(self.config.repo_path, self.git, source_commit)
            rejections = resolver.find_rejections()

            if rejections:
                logger.debug(f"Found {len(rejections)} rejection files")
                for rej in rejections:
                    logger.debug(f"  - {rej.relative_to(self.config.repo_path)}")
            else:
                logger.debug("No rejection files found - patch applied cleanly")

            return TrialResult(
                source_commit=source_commit,
                base_commit=base_commit,
                success=True,
                rejection_count=len(rejections),
                rejection_files=rejections,
            )

        except GitOperationError as e:
            logger.debug(f"Git operation error during trial: {e}")
            return TrialResult(
                source_commit=source_commit,
                base_commit=base_commit,
                success=False,
                rejection_count=-1,
                rejection_files=[],
                error_message=str(e),
            )
        except Exception as e:
            logger.debug(f"Unexpected error during trial: {e}")
            return TrialResult(
                source_commit=source_commit,
                base_commit=base_commit,
                success=False,
                rejection_count=-1,
                rejection_files=[],
                error_message=str(e),
            )

    def complete_patch_application(
        self,
        source_commit: str,
        base_commit: str,
        skip_resolution: bool = False,
        resume: bool = False,
    ) -> int:
        """Complete patch application workflow.

        Assumes patch has already been applied. Executes steps 5-9:
        - Find and resolve rejection files
        - Stage changes
        - Create git note
        - Verify git note
        - Cleanup

        Args:
            source_commit: Source commit with patch.
            base_commit: Base commit to apply patch to.
            skip_resolution: Skip automatic conflict resolution.
            resume: Resume from last checkpoint if it exists.

        Returns:
            Exit code (0 for success, non-zero for failure).
        """
        try:
            # Determine starting step
            start_step = 5
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
                    logger.warning("Checkpoint validation failed, starting from step 5")
                    start_step = 5
            elif self.checkpoint.exists():
                logger.warning("Existing checkpoint found but resume not requested")
                print("\nWarning: Existing checkpoint found.")
                print("Run with --resume to continue from where it failed,")
                print("or remove .workflow_checkpoint.json to start fresh.\n")
                return 1

            # Step 4: Find and resolve rejections
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
                    print("\nPlease resolve the following rejection files:")
                    for rej_file in rejections:
                        print(f"  - {rej_file.relative_to(self.config.repo_path)}")
                    print("\nAfter resolving all conflicts:")
                    print("  1. Review all changes")
                    print("  2. Test the patched code")
                    print("  3. Run: git add -A")
                    print(
                        "  4. Run: python main.py apply {} {} --resume".format(
                            source_commit, base_commit
                        )
                    )
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

    def execute(
        self, source_commit: str, base_commit: str, skip_resolution: bool = False, resume: bool = False
    ) -> int:
        """Execute the patch application workflow.

        Uses modularized trial and completion phases:
        - Trial phase: Test if patch can be applied (steps 1-4)
        - Completion phase: Complete the workflow (steps 5-9)

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

            # If resuming, skip trial and go straight to completion
            if resume and self.checkpoint.exists():
                logger.info("Resuming from checkpoint, skipping trial phase")
                return self.complete_patch_application(
                    source_commit, base_commit, skip_resolution, resume=True
                )

            # Check for existing checkpoint (no resume flag)
            if self.checkpoint.exists():
                logger.warning("Existing checkpoint found but resume not requested")
                print("\nWarning: Existing checkpoint found.")
                print("Run with --resume to continue from where it failed,")
                print("or remove .workflow_checkpoint.json to start fresh.\n")
                return 1

            # Pre-check: Validate no existing git note on target commit
            logger.info("Checking for existing git note on target commit")
            existing_note = self.git.get_git_note(base_commit)
            if existing_note:
                raise WorkflowError(
                    f"Git note already exists for target commit {base_commit}. "
                    "Cannot proceed - the target commit already has a patch note. "
                    "Choose a different target commit or remove the existing note with:\n"
                    f"  git notes --ref={self.config.notes_ref} remove {base_commit}"
                )

            # Trial phase: Test if patch can be applied
            logger.info("Trialing patch application")
            trial_result = self.trial_patch_application(source_commit, base_commit)

            if not trial_result.success:
                logger.error(f"Patch trial failed: {trial_result.error_message}")
                print(f"\nPatch trial failed: {trial_result.error_message}\n")
                return 1

            logger.info(f"Patch trial successful ({trial_result.rejection_count} rejections)")

            # Completion phase: Complete the workflow
            logger.info("Completing patch application workflow")
            return self.complete_patch_application(
                source_commit, base_commit, skip_resolution, resume=False
            )

        except GitOperationError as e:
            logger.error(f"Git operation failed: {e}")
            return 1
        except WorkflowError as e:
            logger.error(f"Workflow error: {e}")
            return 1
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
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
