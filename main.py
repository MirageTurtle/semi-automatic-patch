#!/usr/bin/env python3
"""
Semi-Automatic Patch Application Tool

Applies patches from commit A to commit B with automatic conflict resolution
and manual verification using git notes and Claude Code integration.
"""

import argparse
import sys
from pathlib import Path

from src.workflow import PatchApplicationWorkflow
from src.config import Config
from src.utils import setup_logging
from src.checkpoint import Checkpoint


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Semi-automatic patch application from git notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Apply patch from commit A to commit B
  python main.py apply abc123 def456

  # Resume from last checkpoint (if workflow failed)
  python main.py apply abc123 def456 --resume

  # Show git note from commit
  python main.py show abc123

  # Create git note from changes
  python main.py create-note
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Apply command
    apply_parser = subparsers.add_parser(
        "apply", help="Apply patch from source commit to base commit"
    )
    apply_parser.add_argument(
        "source_commit", help="Source commit with patch in git notes (commit A)"
    )
    apply_parser.add_argument(
        "base_commit", help="Base commit to apply patch to (commit B)"
    )
    apply_parser.add_argument("--repo", default=".", help="Git repository path")
    apply_parser.add_argument(
        "--notes-ref", default="krr-patch", help="Git notes reference"
    )
    apply_parser.add_argument(
        "--skip-resolution",
        action="store_true",
        help="Skip automatic conflict resolution",
    )
    apply_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint if workflow was interrupted",
    )
    apply_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Show command
    show_parser = subparsers.add_parser("show", help="Show git note for a commit")
    show_parser.add_argument("commit", help="Commit to show notes for")
    show_parser.add_argument("--repo", default=".", help="Git repository path")
    show_parser.add_argument(
        "--notes-ref", default="krr-patch", help="Git notes reference"
    )

    # Create note command
    create_parser = subparsers.add_parser(
        "create-note", help="Create git note from current changes"
    )
    create_parser.add_argument(
        "commit", nargs="?", help="Commit to attach note to (defaults to HEAD)"
    )
    create_parser.add_argument("--repo", default=".", help="Git repository path")
    create_parser.add_argument(
        "--notes-ref", default="krr-patch", help="Git notes reference"
    )

    # Clean checkpoint command
    clean_parser = subparsers.add_parser(
        "clean-checkpoint", help="Clear workflow checkpoint (for debugging)"
    )
    clean_parser.add_argument("--repo", default=".", help="Git repository path")

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    if not args.command:
        print("Error: No command specified. Use --help for usage information.")
        return 1

    # Setup logging
    setup_logging(verbose=getattr(args, "verbose", False))

    # Initialize config
    config = Config(repo_path=Path(args.repo), notes_ref=args.notes_ref)

    try:
        if args.command == "apply":
            workflow = PatchApplicationWorkflow(config)
            return workflow.execute(
                source_commit=args.source_commit,
                base_commit=args.base_commit,
                skip_resolution=args.skip_resolution,
                resume=args.resume,
            )

        elif args.command == "show":
            workflow = PatchApplicationWorkflow(config)
            patch = workflow.show_git_note(args.commit)
            print(patch)
            return 0

        elif args.command == "create-note":
            workflow = PatchApplicationWorkflow(config)
            commit = args.commit or "HEAD"
            workflow.create_git_note(commit)
            print(f"Git note created for {commit}")
            return 0

        elif args.command == "clean-checkpoint":
            checkpoint = Checkpoint(Path(args.repo))
            if checkpoint.exists():
                checkpoint.clear()
                print("Checkpoint cleared successfully")
            else:
                print("No checkpoint found")
            return 0

        else:
            print(f"Error: Unknown command '{args.command}'")
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
