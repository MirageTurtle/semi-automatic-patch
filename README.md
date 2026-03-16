# Semi-Automatic Patch Application Tool

A Python-based CLI tool for applying patches from one Git commit to another with automatic conflict detection and support for manual resolution.

## Usage

### Typical Workflow

The tool is designed for applying patches from a commit list file with automatic candidate selection:

#### Step 0: Patch the first commit

You should apply a patch for at least one commit in your commit file, as the start point.

#### Step 1: Batch Apply from File

Start batch processing from a commit list file (the file contains commits that have git notes with patches):

```bash
uv run python main.py apply-from-file <commit_file> <base_commit> \
    --repo <linux_repo> \
    --max-candidates 5
```

This will:
- Read commits from the file
- For each commit, search previous commits (that have git notes with patches) for candidates (you can use `--search-forward` for subsequent commits in the list file)
- Try each candidate and select the one with minimal conflicts if it fails
- Stop when conflicts are found that need manual resolution

#### Step 2: Manual Conflict Resolution

When the program stops due to conflicts:
- It shows the conflicts from candidate patch(es)
- User chooses one commit (might with minimal conflicts)

#### Step 3: Resume Workflow

Manually applies the patch and resumes after resolving conflicts (both are the following commands):

```bash
uv run python main.py apply <source_commit_with_git_note_patch> <base_commit> \
    --repo <linux_repo> \
    --resume
```

### Command Reference

| Command | Description |
|---------|-------------|
| `apply <source> <base>` | Apply patch from source commit to base commit |
| `apply-from-file <file> <base>` | Batch process from commit list file |
| `show <commit>` | Display patch stored in commit's git note |
| `create-note [commit]` | Create git note from current changes |
| `clean-checkpoint` | Remove workflow checkpoint file |

### Common Options

| Option | Description |
|--------|-------------|
| `--repo <path>` | Path to Git repository |
| `--notes-ref <ref>` | Git notes reference (default: `krr-patch`) |
| `--max-candidates <n>` | Max patch candidates to try (default: 3) |
| `--search-forward` | Search candidates in subsequent commits |
| `--resume` | Resume from last checkpoint |
| `--verbose`, `-v` | Enable verbose logging |

## Project Structure

```
semi-automatic-patch/
├── main.py                   # CLI entry point
├── pyproject.toml           # Project configuration
├── README.md                # This file
├── uv.lock                  # Locked dependencies
├── .gitignore               # Git ignore rules
├── src/
│   ├── __init__.py
│   ├── config.py            # Configuration dataclass
│   ├── checkpoint.py        # Checkpoint management for error recovery
│   ├── git_ops.py           # Low-level Git operations
│   ├── conflict_resolver.py # Conflict resolution logic
│   ├── workflow.py          # Main workflow orchestration
│   ├── candidate_selector.py # Multi-candidate patch search
│   ├── commit_manager.py    # Commit list file management
│   └── utils.py             # Utility functions
```

## Workflow for command `apply-from-file`

```
┌─────────────────────────────────────────────────────────────────┐
│                    Patch Application Workflow                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Working Directory Validation                                │
│     - Check for uncommitted changes                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Checkout Base Commit                                        │
│     - Switch to target commit                                   │
│     - Validate git note doesn't exist on target                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Retrieve and Apply Patch                                    │
│     - Get patch from source commit's git notes                  │
│     - Apply with git apply --reject                             │
└─────────────────────────────────────────────────────────────────┘
                        │               ▲
                        ▼               │ Has rejections & candidates
┌─────────────────────────────────────────────────────────────────┐   Has rejections      ┌──────────────────────────────────┐
│  4. Conflict Detection                                          │ ───────────────── ▶   │  5. Manually Conflict Resolution │
│     - Scan for .rej files (rejection files)                     │   & no candidates     │     - Manual intervention        │
└─────────────────────────────────────────────────────────────────┘                       └──────────────────────────────────┘
                                │
                  No rejections │
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Stage and Create Git Note                                   │
│     - git add -A                                                │
│     - Create git note with resolved patch                       │
│     - Verify note created successfully                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Cleanup                                                     │
│     - Hard reset                                                │
│     - Remove untracked files                                    │
│     - Clear checkpoint                                          │
└─────────────────────────────────────────────────────────────────┘
```
