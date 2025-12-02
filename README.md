# Semi-Automatic Patch Application Tool

A Python-based CLI tool for applying patches from one Git commit to another with automatic conflict detection and support for manual resolution. Designed to handle complex patch applications, particularly useful for Linux kernel development where patches may not apply cleanly across different kernel versions.

## Features

- **Git Notes Integration**: Store and retrieve patches using Git's notes system
- **Automatic Conflict Detection**: Identifies and reports patch application conflicts
- **Structured Workflow**: Step-by-step patch application process with clear status reporting
- **Manual Verification Support**: Guides users through manual conflict resolution when needed
- **Clean State Management**: Automatic working directory validation and cleanup
- **Error Recovery**: Checkpoint-based resumption allows continuing from the point of failure
- **Detailed Logging**: Debug-level logging available for troubleshooting

## Prerequisites

- Python 3.13 or higher
- Git with notes support
- A valid Git repository

## Installation

Clone the repository and install dependencies using `uv`:

```bash
git clone <repository-url>
cd semi-automatic-patch
uv sync
```

## Usage

### Commands

#### Apply a Patch

Apply a patch from a source commit (containing the patch in git notes) to a base commit:

```bash
uv run python main.py apply <source-commit> <base-commit>
```

**Arguments:**
- `source-commit`: The commit containing the patch stored in git notes
- `base-commit`: The target commit where the patch will be applied

**Options:**
- `--repo <path>`: Path to the Git repository (default: current directory)
- `--notes-ref <ref>`: Git notes reference name (default: `krr-patch`)
- `--skip-resolution`: Skip automatic conflict resolution
- `--resume`: Resume from the last checkpoint if the workflow was interrupted
- `--verbose` or `-v`: Enable verbose logging

**Example:**
```bash
uv run python main.py apply abc123def def456abc --verbose
```

**Resume after failure:**
```bash
uv run python main.py apply abc123def def456abc --resume
```

#### Show a Git Note

Display the patch stored in a commit's git note:

```bash
uv run python main.py show <commit>
```

**Arguments:**
- `commit`: The commit to retrieve notes from

**Options:**
- `--repo <path>`: Path to the Git repository (default: current directory)
- `--notes-ref <ref>`: Git notes reference name (default: `krr-patch`)

**Example:**
```bash
uv run python main.py show abc123def
```

#### Create a Git Note

Create a git note from the current uncommitted changes:

```bash
uv run python main.py create-note [commit]
```

**Arguments:**
- `commit`: (Optional) The commit to attach the note to (default: HEAD)

**Options:**
- `--repo <path>`: Path to the Git repository (default: current directory)
- `--notes-ref <ref>`: Git notes reference name (default: `krr-patch`)

**Example:**
```bash
uv run python main.py create-note HEAD
```

#### Clear Workflow Checkpoint

Remove the workflow checkpoint file (useful for debugging or forcing a fresh start):

```bash
uv run python main.py clean-checkpoint
```

**Options:**
- `--repo <path>`: Path to the Git repository (default: current directory)

**Example:**
```bash
uv run python main.py clean-checkpoint
```

## Workflow

The patch application follows this workflow:

### Step 1: Working Directory Validation
Ensures the working directory is clean before proceeding.

### Step 2: Checkout Base Commit
Switches to the target commit where the patch will be applied.

### Step 3: Retrieve and Apply Patch
- Retrieves the patch from git notes of the source commit
- Applies the patch using `git apply --reject` to capture any failures

### Step 4: Detect Conflicts
Scans for `.rej` files (rejection files) that indicate where the patch failed to apply cleanly.

### Step 5: Resolve Conflicts
For each rejection file found:
- Analyzes the conflict context
- Prepares conflict resolution information
- Reports which files need manual verification if automatic resolution cannot be performed

### Step 6: Stage and Create Git Note
Once all conflicts are resolved:
- Stages all changes with `git add -A`
- Creates a new git note from the resolved patch
- Verifies the note was created successfully

### Step 7: Cleanup
Performs a hard reset and removes untracked files to return to a clean state.

## Error Recovery and Resumption

The tool supports resuming from the point of failure through a checkpoint system:

### How It Works

- **Automatic Checkpoints**: After each major step completes successfully, a checkpoint is saved to `.workflow_checkpoint.json`
- **Error Handling**: If any error occurs, the process stops immediately without cleaning up the working directory
- **Resume Support**: Use the `--resume` flag to continue from where it failed, skipping already-completed steps
- **Checkpoint Validation**: The checkpoint is validated to ensure it matches the current source and base commits

### Workflow on Error

1. Process runs and encounters an error at step N
2. Working directory is left untouched (no cleanup performed)
3. Checkpoint file `.workflow_checkpoint.json` is saved with the last completed step
4. User receives an error message and can investigate/fix the issue
5. Run the command again with `--resume` to continue from step N+1

### Example Scenario

```bash
# Initial run encounters an error at step 5
$ uv run python main.py apply abc123 def456
Error: Git operation failed: <details>

# Working directory is preserved, checkpoint saved
# User fixes the issue (e.g., resolves a merge conflict manually)

# Resume the workflow from step 6
$ uv run python main.py apply abc123 def456 --resume
Resuming workflow from step 6
... (continues with staging, git notes, etc.)
Workflow completed successfully
```

### Checkpoint Management

- **Automatic Cleanup**: Successful workflow completion automatically removes the checkpoint
- **Manual Cleanup**: Use `clean-checkpoint` command to manually remove the checkpoint file

```bash
uv run python main.py clean-checkpoint
```

## Configuration

Configuration is managed through command-line arguments or the `Config` class in `src/config.py`:

| Option | Default | Description |
|--------|---------|-------------|
| `repo_path` | `.` | Path to the Git repository |
| `notes_ref` | `krr-patch` | Git notes reference name |
| `claude_model` | `claude-opus` | Claude model for integration (future feature) |

## Project Structure

```
semi-automatic-patch/
├── main.py                   # CLI entry point
├── pyproject.toml           # Project configuration
├── README.md                # This file
└── src/
    ├── __init__.py
    ├── config.py            # Configuration dataclass
    ├── checkpoint.py        # Checkpoint management for error recovery
    ├── git_ops.py           # Low-level Git operations
    ├── conflict_resolver.py # Conflict resolution logic
    ├── workflow.py          # Main workflow orchestration
    └── utils.py             # Utility functions
```

## Module Documentation

### `main.py`
Entry point for the CLI. Handles argument parsing and command routing.

**Key Functions:**
- `parse_arguments()`: Parses command-line arguments
- `main()`: Main entry point that executes the selected command

### `src/checkpoint.py`
Checkpoint management for workflow error recovery and resumption.

**Key Class:**
- `Checkpoint`: Manages workflow checkpoints for resumption capability

**Key Methods:**
- `save()`: Save workflow checkpoint after step completion
- `load()`: Load existing checkpoint
- `exists()`: Check if checkpoint file exists
- `clear()`: Remove checkpoint file after successful completion
- `validate_checkpoint()`: Validate checkpoint matches current parameters
- `get_next_step()`: Determine next step to execute based on checkpoint

### `src/workflow.py`
Orchestrates the complete patch application workflow.

**Key Class:**
- `PatchApplicationWorkflow`: Manages the entire patch application process

**Key Methods:**
- `execute()`: Runs the full workflow
- `show_git_note()`: Retrieves a git note
- `create_git_note()`: Creates a git note from current changes

### `src/git_ops.py`
Low-level Git operations abstraction.

**Key Class:**
- `GitOps`: Handles all Git commands

**Key Methods:**
- `checkout()`: Switch to a commit
- `apply_patch()`: Apply patch with rejection handling
- `get_git_note()`: Retrieve patch from git notes
- `create_git_note()`: Create a git note
- `stage_changes()`: Stage all changes
- `reset_hard()`: Reset working directory

### `src/conflict_resolver.py`
Handles detection and resolution of patch conflicts.

**Key Class:**
- `ConflictResolver`: Manages conflict resolution

**Key Methods:**
- `find_rejections()`: Find all `.rej` files
- `resolve_rejection()`: Resolve a single rejection
- `resolve_all_rejections()`: Resolve all rejections

### `src/config.py`
Configuration management.

**Key Class:**
- `Config`: Dataclass for workflow configuration

### `src/utils.py`
Utility functions and helpers.

**Key Functions:**
- `setup_logging()`: Configure logging
- `find_rejection_files()`: Locate rejection files
- `get_logger()`: Get a logger instance

## Exit Codes

- `0`: Successful execution
- `1`: Failure during execution

## Error Handling

The tool provides detailed error messages for common issues:

| Issue | Cause | Resolution |
|-------|-------|-----------|
| "Working directory is not clean" | Uncommitted changes exist | Commit or stash changes |
| "No git note found" | Source commit has no patch | Create a git note first |
| "Not a git repository" | Invalid repository path | Verify the repository path |
| "Rejection files found" | Patch conflicts detected | Resolve conflicts manually |

## Development

### Code Formatting

The project uses `ruff` for code formatting:

```bash
uv run ruff check src/ main.py
uv run ruff format src/ main.py
```

### Testing

To add tests, use pytest (to be installed as dev dependency):

```bash
uv add --dev pytest
```

### Project Management

All dependencies are managed through `uv`.

## License

[Add license information]

## Contributing

[Add contribution guidelines]

