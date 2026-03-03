#!/bin/bash

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
YELLOW='\033[33m'
GREEN='\033[32m'
RED='\033[31m'
BLUE='\033[34m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Path: src/ontobdc/dev/commit.sh -> ../../../.. -> ontobdc-stack/
# IMPORTANT: Adjust this relative path if the script location changes!
# Currently: ontobdc-wip/src/ontobdc/dev/commit.sh
# Target: ontobdc-stack (root of the monorepo/workspace)
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

TERM_WIDTH=$(tput cols)
if [ -z "$TERM_WIDTH" ]; then TERM_WIDTH=80; fi
INNER_WIDTH=$((TERM_WIDTH - 2))

# Generate horizontal lines
HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))
FULL_HLINE=$(printf '─%.0s' $(seq 1 $TERM_WIDTH))

# --- Functions ---
print_message_box() {
    # Simple message box implementation
    local COLOR="$1"
    local TITLE_TYPE="$2"
    local TITLE_TEXT="$3"
    local MSG_TEXT="$4"
    
    echo -e "${COLOR}╭${HLINE}╮${RESET}"
    echo -e "${COLOR}│${RESET} >_ ${BOLD}${COLOR}${TITLE_TYPE}${RESET} ${TITLE_TEXT}"
    echo -e "${COLOR}│${RESET}"
    echo -e "${COLOR}│${RESET} ${MSG_TEXT}"
    echo -e "${COLOR}╰${HLINE}╯${RESET}"
}

if [ -z "$1" ]; then
    echo -e "${RED}Error: Missing commit message${RESET}"
    echo -e "Usage: ontobdc commit \"Your message\""
    exit 1
fi

MSG="$1"

echo -e "${CYAN}Starting commit process...${RESET}"
echo -e "${GRAY}Root Directory: ${ROOT_DIR}${RESET}"
echo -e "${GRAY}Message: ${WHITE}\"$MSG\"${RESET}"
echo ""

# Function to perform git operations in a directory
process_repo() {
    local REPO_PATH="$1"
    local REPO_NAME=$(basename "$REPO_PATH")
    
    # Skip if directory doesn't exist
    if [ ! -d "$REPO_PATH" ]; then
        return
    fi
    
    # Check if it's a git repo
    if [ ! -d "$REPO_PATH/.git" ] && [ ! -f "$REPO_PATH/.git" ]; then
        return
    fi

    echo -e "${YELLOW}❯ Processing ${REPO_NAME}${RESET}"
    
    # Run in subshell to preserve CWD
    (
        cd "$REPO_PATH" || exit
        
        # Stash current branch name
        BRANCH=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)
        
        # Add all changes
        git add . > /dev/null 2>&1
        
        # Check for changes
        if ! git diff-index --quiet HEAD --; then
            git commit -m "$MSG" > /dev/null 2>&1
            echo -e "  ${GREEN}✓ Committed changes${RESET}"
            
            # Push if remote exists
            if git remote | grep -q "."; then
                if git push > /dev/null 2>&1; then
                    echo -e "  ${GREEN}✓ Pushed to remote${RESET}"
                else
                     # Try setting upstream
                     if git push --set-upstream origin "$BRANCH" > /dev/null 2>&1; then
                        echo -e "  ${GREEN}✓ Pushed to remote (set upstream)${RESET}"
                     else
                        echo -e "  ${RED}✗ Push failed${RESET}"
                     fi
                fi
            else
                echo -e "  ${GRAY}• No remote repository found (skipping push)${RESET}"
            fi
        else
            echo -e "  ${GRAY}• No changes to commit${RESET}"
        fi
    )
}

# 1. Process Submodules explicitly detected via .gitmodules
# This is more robust than `git submodule foreach` which might skip if not initialized
if [ -f "${ROOT_DIR}/.gitmodules" ]; then
    # Extract paths from .gitmodules
    # Format: 	path = ontobdc-wip
    SUBMODULES=$(grep "path =" "${ROOT_DIR}/.gitmodules" | awk '{print $3}')
    
    for SUB in $SUBMODULES; do
        process_repo "${ROOT_DIR}/${SUB}"
    done
fi

# 2. Process ontobdc-wip explicitly if not in .gitmodules (development fallback)
if [ -d "${ROOT_DIR}/ontobdc-wip" ]; then
    # Check if we already processed it (simple string check)
    if [[ "$SUBMODULES" != *"ontobdc-wip"* ]]; then
        process_repo "${ROOT_DIR}/ontobdc-wip"
    fi
fi

# 3. Process ontobdc-core explicitly (core distribution)
if [ -d "${ROOT_DIR}/ontobdc-core" ]; then
    if [[ "$SUBMODULES" != *"ontobdc-core"* ]]; then
        process_repo "${ROOT_DIR}/ontobdc-core"
    fi
fi

# 4. Process Root Repository (Last)
process_repo "${ROOT_DIR}"

echo ""
echo -e "${GREEN}Success! Commit finished.${RESET}"
