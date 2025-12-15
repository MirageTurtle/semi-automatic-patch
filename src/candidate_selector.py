"""
Candidate selector module for multi-candidate patch search.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .utils import get_logger
from .workflow import PatchApplicationWorkflow, TrialResult
from .commit_manager import CommitManager, CommitManagerError

logger = get_logger(__name__)


@dataclass
class CandidateSearchResult:
    """Result of multi-candidate patch search."""

    best_candidate: Optional[str]
    trial_results: List[TrialResult]
    selection_reason: str
    patch_applied: bool = False  # True if best_candidate's patch is currently applied


class CandidateSelector:
    """Select the best patch candidate from multiple options."""

    def __init__(
        self,
        commit_manager: CommitManager,
        workflow: PatchApplicationWorkflow,
    ):
        """Initialize candidate selector.

        Args:
            commit_manager: CommitManager for commit navigation.
            workflow: PatchApplicationWorkflow for patch application.
        """
        self.commit_manager = commit_manager
        self.workflow = workflow

    def find_candidates(
        self, base_commit: str, max_candidates: int, search_forward: bool = False
    ) -> List[str]:
        """Find candidates from base_commit.

        Searches the commit list for up to max_candidates commits that have git notes.
        By default searches backwards (previous commits). With search_forward=True,
        searches forwards (subsequent commits).

        Args:
            base_commit: Target commit (commit B).
            max_candidates: Maximum number of candidates to find.
            search_forward: If True, search forward in commits. If False (default), search backward.

        Returns:
            List of candidate commits in order (nearest first).
        """
        candidates = []

        try:
            base_index = self.commit_manager.find_commit_index(base_commit)
        except CommitManagerError as e:
            logger.error(f"Could not find base commit: {e}")
            return candidates

        direction = "forward" if search_forward else "backward"
        logger.debug(f"Searching {direction} for candidates")

        # Search up to max_candidates positions
        for i in range(1, max_candidates + 1):
            if search_forward:
                # Search forward (increasing indices)
                next_index = base_index + i
                if next_index >= len(self.commit_manager.commits):
                    logger.debug(f"Reached end of commit list after {i - 1} candidates")
                    break
                candidate = self.commit_manager.commits[next_index]
            else:
                # Search backward (decreasing indices)
                next_index = base_index - i
                if next_index < 0:
                    logger.debug(f"Reached beginning of commit list after {i - 1} candidates")
                    break
                candidate = self.commit_manager.commits[next_index]

            # Check if candidate has git note
            note = self.workflow.git.get_git_note(candidate)
            if not note:
                logger.debug(f"Skipping {candidate}: no git note")
                continue

            candidates.append(candidate)
            logger.debug(f"Found candidate {len(candidates)}: {candidate}")

        return candidates

    def select_best_candidate(
        self, base_commit: str, max_candidates: int, search_forward: bool = False
    ) -> CandidateSearchResult:
        """Select the best patch candidate from available options.

        Searches through the commit list for candidates with git notes, tries each one,
        and selects:
        - If any succeed cleanly: the first one with 0 rejections (stops early)
        - Otherwise: the one with the fewest rejections

        The selected candidate's patch is left applied in the working directory.
        Other candidates are cleaned up after testing.

        Args:
            base_commit: Target commit (commit B).
            max_candidates: Maximum number of candidates to try.
            search_forward: If True, search forward in commits. If False (default), search backward.

        Returns:
            CandidateSearchResult with selection information and patch_applied flag.
        """
        direction = "forward" if search_forward else "backward"
        logger.info(f"Searching {direction} for best patch candidate (max: {max_candidates})")

        # Step 1: Find candidates
        candidates = self.find_candidates(base_commit, max_candidates, search_forward=search_forward)

        if not candidates:
            logger.warning("No valid candidates found with git notes")
            search_dir = "forward" if search_forward else "backward"
            return CandidateSearchResult(
                best_candidate=None,
                trial_results=[],
                selection_reason=f"No candidates with git notes found (searched {max_candidates} commits {search_dir})",
                patch_applied=False,
            )

        logger.info(f"Found {len(candidates)} valid candidates")

        # Step 2: Trial each candidate
        trial_results = []
        clean_apply_result = None

        for i, candidate in enumerate(candidates, 1):
            logger.info(f"Trialing candidate {i}/{len(candidates)}: {candidate}")

            try:
                result = self.workflow.trial_patch_application(candidate, base_commit)
                trial_results.append(result)

                if result.success and result.rejection_count == 0:
                    logger.info(f"Clean apply found: {candidate} (0 rejections)")
                    clean_apply_result = result
                    # Early termination: found clean apply, keep it applied
                    logger.info("Stopping early - clean apply found")
                    break
                elif result.success:
                    logger.info(f"Trial succeeded with {result.rejection_count} rejections")
                    # Cleanup for next trial
                    try:
                        self.workflow.git.reset_hard()
                        self.workflow.git.clean_untracked()
                    except Exception as e:
                        logger.warning(f"Cleanup after trial failed: {e}")
                else:
                    logger.warning(f"Trial failed: {result.error_message}")
                    # Cleanup for next trial even on failure
                    try:
                        self.workflow.git.reset_hard()
                        self.workflow.git.clean_untracked()
                    except Exception as e:
                        logger.warning(f"Cleanup after failed trial: {e}")

            except Exception as e:
                logger.error(f"Trial raised exception: {e}")
                # Cleanup and continue to next candidate
                try:
                    self.workflow.git.reset_hard()
                    self.workflow.git.clean_untracked()
                except Exception as cleanup_error:
                    logger.warning(f"Cleanup after exception: {cleanup_error}")

        # Step 3: Select best candidate - only if clean apply found
        if clean_apply_result:
            best = clean_apply_result
            reason = f"Clean apply with 0 rejections (tried {len(trial_results)} candidates)"
            patch_applied = True  # Patch is still applied
            logger.info(f"Selected {best.source_commit} - {reason} (patch applied)")
        else:
            # No clean candidate found - stop here
            logger.warning("No candidate with clean apply (0 rejections) found")

            # Cleanup workspace since no suitable candidate
            try:
                self.workflow.git.reset_hard()
                self.workflow.git.clean_untracked()
            except Exception as e:
                logger.warning(f"Final cleanup failed: {e}")

            # Report candidates that were tried but had conflicts
            if trial_results:
                rejection_summary = ", ".join(
                    [f"{t.source_commit}({t.rejection_count} rejections)" for t in trial_results if t.success]
                )
                reason = f"No clean candidate found. Tried {len(trial_results)}: {rejection_summary}"
            else:
                reason = "All candidates failed during trial"

            logger.error(f"No clean candidate: {reason}")
            return CandidateSearchResult(
                best_candidate=None,
                trial_results=trial_results,
                selection_reason=reason,
                patch_applied=False,
            )

        return CandidateSearchResult(
            best_candidate=best.source_commit,
            trial_results=trial_results,
            selection_reason=reason,
            patch_applied=patch_applied,
        )
