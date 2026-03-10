#!/bin/bash

# Configuration
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${SOURCE_DIR}/../core"

# Resolve absolute path for Target
TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd)"

# Define Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'
GRAY='\033[0;90m'

echo -e "${BOLD}OntoBDC Sync Tool${RESET}"
echo -e "Source (WIP):  ${BLUE}${SOURCE_DIR}${RESET}"
echo -e "Target (Core): ${BLUE}${TARGET_DIR}${RESET}"
echo ""

if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}Error: Target directory not found at ${TARGET_DIR}${RESET}"
    exit 1
fi

# Construct Rsync Filter Arguments
# Rsync processes filters in order: first match wins.
# So we must list EXCLUDES BEFORE INCLUDES.

RSYNC_ARGS=()

# 1. Global Exclusions (High Priority)
# These should NEVER be synced, even if inside an included folder
RSYNC_ARGS+=(--exclude='__pycache__/')
RSYNC_ARGS+=(--exclude='__pycache__')
RSYNC_ARGS+=(--exclude='*.pyc')
RSYNC_ARGS+=(--exclude='.DS_Store')
RSYNC_ARGS+=(--exclude='.venv/')
RSYNC_ARGS+=(--exclude='.git/')

# 2. Exclude files from .gitignore (Source) if it exists
GITIGNORE_FILE="${SOURCE_DIR}/.gitignore"
if [ -f "$GITIGNORE_FILE" ]; then
    RSYNC_ARGS+=(--exclude-from="$GITIGNORE_FILE")
fi

# 3. List of files/directories to include (The Source of Truth)
INCLUDES=(
    "src/"
    "pyproject.toml"
    "README.md"
    "LICENSE"
    "message_box.sh"
    ".github/"
    "docs/"
    "tests/"
)

# 4. Include the specific top-level items
for item in "${INCLUDES[@]}"; do
    RSYNC_ARGS+=(--include="$item")
    # If it's a directory, we need to include everything inside it recursively
    if [[ "$item" == */ ]]; then
        RSYNC_ARGS+=(--include="${item}***")
    fi
done

# 5. Exclude everything else at the root level (Strict Mode)
# This MUST be the last rule
RSYNC_ARGS+=(--exclude='*')

# Parse arguments
DRY_RUN=true

if [[ "$1" == "--run" || "$1" == "--sync" ]]; then
    DRY_RUN=false
fi

echo -e "${YELLOW}Analyzing differences...${RESET}"

# Function to colorize rsync output
colorize_output() {
    while IFS= read -r line; do
        if [[ "$line" == *deleting* ]]; then
             # Deletion: Red
             echo -e "${RED}${line}${RESET}"
        elif [[ "$line" == ">f+++++++++"* ]]; then
             # New file: Green
             echo -e "${GREEN}${line}${RESET}"
        elif [[ "$line" == "cd+++++++++"* ]]; then
             # New directory: Green
             echo -e "${GREEN}${line}${RESET}"
        elif [[ "$line" == ">f"* ]]; then
             # Modified file: Yellow
             echo -e "${YELLOW}${line}${RESET}"
        else
             # Default/Unchanged
             echo "$line"
        fi
    done
}

if [ "$DRY_RUN" = true ]; then
    echo -e "${GRAY}(Dry Run Mode - No changes will be made)${RESET}"
    echo ""
    
    # Run Rsync and pipe to colorizer
    rsync -avc -i --dry-run --delete --prune-empty-dirs \
        "${RSYNC_ARGS[@]}" \
        "$SOURCE_DIR/" "$TARGET_DIR/" | colorize_output
        
    echo ""
    echo -e "${YELLOW}Legend:${RESET}"
    echo -e "  ${GREEN}>f+++++++++${RESET} : New file"
    echo -e "  ${YELLOW}>f...${RESET}       : Modified file"
    echo -e "  ${RED}*deleting${RESET}   : Deleted file"
    echo ""
    echo -e "To execute the sync, run: ${BOLD}./sync_core.sh --run${RESET}"
else
    echo -e "${YELLOW}Synchronizing files...${RESET}"
    echo ""
    
    # Run Rsync real mode
    rsync -avc -i --delete --prune-empty-dirs \
        "${RSYNC_ARGS[@]}" \
        "$SOURCE_DIR/" "$TARGET_DIR/" | colorize_output
        
    echo ""
    echo -e "${GREEN}✓ Synchronization Complete.${RESET}"
fi
