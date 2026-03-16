#!/usr/bin/env bash

# Script to process commit hashes from a file
# Starting from a specific hash, perform git note operations on each commit

set -euo

# Configuration
START_HASH="489fa31ea873282b41046d412ec741f93946fc2d" # hard-coded
REPO_PATH="./linux"                                   # hard-coded

# Check if file argument is provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <commit_hash_file>"
    exit 1
fi

HASH_FILE="$1"

# Check if file exists
if [ ! -f "$HASH_FILE" ]; then
    echo "Error: File '$HASH_FILE' not found"
    exit 1
fi

# Check if repo path exists
if [ ! -d "$REPO_PATH/.git" ]; then
    echo "Error: '$REPO_PATH' is not a valid git repository"
    exit 1
fi

# Helper function to run git commands in the repo
git_repo() {
    git -C "$REPO_PATH" "$@"
}

# Flag to track if we've reached the starting hash
started=false

# Read the file line by line
while IFS= read -r commit_hash || [ -n "$commit_hash" ]; do
    # Skip empty lines
    if [ -z "$commit_hash" ]; then
        continue
    fi

    # Trim whitespace
    commit_hash=$(echo "$commit_hash" | tr -d '[:space:]')

    # Check if we've reached the starting hash
    if [ "$commit_hash" = "$START_HASH" ]; then
        started=true
    fi

    # Skip lines before the starting hash
    if [ "$started" = false ]; then
        echo "Skipping: $commit_hash (before start hash)"
        continue
    fi

    echo "Processing commit: $commit_hash"

    # Process A: checkout, modify note, and verify
    git_repo checkout "$commit_hash"

    # hard-coded
    git_repo notes --ref=krr-patch show $(git_repo rev-parse HEAD) |
        sed 's/vma->vm_flags |= (VM_SHARED| VM_DONTEXPAND | VM_DONTDUMP);/vm_flags_set(vma, VM_SHARED | VM_DONTEXPAND | VM_DONTDUMP);/' |
        git_repo notes --ref=krr-patch add -F - -f

    git_repo notes --ref=krr-patch show $(git_repo rev-parse HEAD) | rg vm_flags_set

    echo "Successfully processed: $commit_hash"
    echo "---"

done <"$HASH_FILE"

echo "All commits processed successfully!"
