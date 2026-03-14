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

# --- Determine Root Directory ---
# The script can run in two modes:
# 1. Dev Mode (from source): Script is deep inside core/src/ontobdc/dev
# 2. Installed Mode (pip): Script is inside site-packages/ontobdc/dev

# Try to find the root by looking for .git or .gitmodules upwards from CWD
# This allows 'ontobdc commit' to work from anywhere within a repo
find_git_root() {
    local DIR="$PWD"
    while [ "$DIR" != "/" ]; do
        if [ -d "$DIR/.git" ] || [ -f "$DIR/.gitmodules" ]; then
            echo "$DIR"
            return 0
        fi
        DIR=$(dirname "$DIR")
    done
    return 1
}

GIT_ROOT=$(find_git_root)

if [ -n "$GIT_ROOT" ]; then
    ROOT_DIR="$GIT_ROOT"
else
    # Fallback to relative path logic if we can't find a git root from CWD
    # This assumes we are running from source structure
    ROOT_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
    
    # Check if this fallback actually points to a git repo
    if [ ! -d "$ROOT_DIR/.git" ] && [ ! -f "$ROOT_DIR/.gitmodules" ]; then
        # If fallback also fails (e.g. installed package running outside a repo),
        # default to CWD but warn
        echo -e "${YELLOW}Warning: Could not detect git repository root. Using current directory.${RESET}"
        ROOT_DIR="$PWD"
    fi
fi


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

LOG_SCRIPT="${SCRIPT_DIR}/../cli/print_log.sh"
if [ -f "$LOG_SCRIPT" ]; then
    bash "$LOG_SCRIPT" "INFO" "Starting commit process..."
    bash "$LOG_SCRIPT" "INFO" "Root Directory: ${ROOT_DIR}"
    bash "$LOG_SCRIPT" "INFO" "Message: ${MSG}"
else
    echo -e "${CYAN}Starting commit process...${RESET}"
    echo -e "${GRAY}Root Directory: ${ROOT_DIR}${RESET}"
    echo -e "${GRAY}Message: ${WHITE}\"$MSG\"${RESET}"
fi
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
    
    # Get current branch name
    local BRANCH=$(cd "$REPO_PATH" && (git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD))

    echo ""
    echo -e "${WHITE}❯ Processing ${REPO_NAME} ${CYAN}(${BRANCH})${RESET}"

    # Run in subshell to preserve CWD
    (
        cd "$REPO_PATH" || exit
        
        # Add all changes
        git add . > /dev/null 2>&1
        bash "$LOG_SCRIPT" "SUCCESS" "   • Added all changes"
        
        # Check for changes
        if ! git diff-index --quiet HEAD --; then
            git commit -m "$MSG" > /dev/null 2>&1
            bash "$LOG_SCRIPT" "SUCCESS" "   • Committed changes"
            
            # Push if remote exists
            if git remote | grep -q "."; then
                PUSH_CMD=(git push)
                REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)
                SSH_KEY_PATH=$(python3 -c "import os, sys
try:
    import yaml
except Exception:
    print('')
    sys.exit(0)
path='${ROOT_DIR}/.__ontobdc__/config.yaml'
try:
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    dev = cfg.get('dev') or {}
    key = (((dev.get('repo') or {}).get('ssh') or {}).get('key_path') or '')
    if not key:
        key = ((((cfg.get('repo') or {}).get('ssh') or {}).get('key_path')) or '')
    print(key if isinstance(key, str) else '')
except Exception:
    print('')
")
                CAN_USE_SSH_KEY=false
                if [ -n "$SSH_KEY_PATH" ]; then
                    if [ -f "$SSH_KEY_PATH" ]; then
                        if [[ "$REMOTE_URL" == git@* || "$REMOTE_URL" == ssh://* ]]; then
                            CAN_USE_SSH_KEY=true
                        fi
                    else
                        bash "$LOG_SCRIPT" "WARN" "  ${YELLOW}!${RESET} SSH key not found at ${SSH_KEY_PATH}"
                    fi
                fi

                PUSH_OUTPUT=$("${PUSH_CMD[@]}" 2>&1)
                PUSH_EXIT=$?
                if [ $PUSH_EXIT -ne 0 ] && [ "$CAN_USE_SSH_KEY" = true ]; then
                    PUSH_OUTPUT=$(GIT_SSH_COMMAND="ssh -i ${SSH_KEY_PATH} -o IdentitiesOnly=yes" "${PUSH_CMD[@]}" 2>&1)
                    PUSH_EXIT=$?
                fi

                if [ $PUSH_EXIT -eq 0 ]; then
                    bash "$LOG_SCRIPT" "SUCCESS" "   • Pushed to remote"
                else
                     # Try setting upstream
                     UPSTREAM_OUTPUT=$("${PUSH_CMD[@]}" --set-upstream origin "$BRANCH" 2>&1)
                     UPSTREAM_EXIT=$?
                     if [ $UPSTREAM_EXIT -ne 0 ] && [ "$CAN_USE_SSH_KEY" = true ]; then
                        UPSTREAM_OUTPUT=$(GIT_SSH_COMMAND="ssh -i ${SSH_KEY_PATH} -o IdentitiesOnly=yes" "${PUSH_CMD[@]}" --set-upstream origin "$BRANCH" 2>&1)
                        UPSTREAM_EXIT=$?
                     fi

                     if [ $UPSTREAM_EXIT -eq 0 ]; then
                        bash "$LOG_SCRIPT" "SUCCESS" "   • Pushed to remote (set upstream)"
                     else
                        bash "$LOG_SCRIPT" "ERROR" "  ${RED}✗${RESET} Push failed"
                     fi
                fi
            else
                bash "$LOG_SCRIPT" "INFO" "  ${GRAY}• No remote repository found (skipping push)${RESET}"
            fi
        else
            bash "$LOG_SCRIPT" "INFO" "  ${GRAY}• No changes to commit${RESET}"
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
if [ -d "${ROOT_DIR}/wip" ]; then
    # Check if we already processed it (simple string check)
    if [[ "$SUBMODULES" != *"wip"* ]]; then
        process_repo "${ROOT_DIR}/wip"
    fi
fi

# 3. Process core explicitly (core distribution)
if [ -d "${ROOT_DIR}/core" ]; then
    if [[ "$SUBMODULES" != *"core"* ]]; then
        process_repo "${ROOT_DIR}/core"
    fi
fi

# 4. Process Root Repository (Last)
process_repo "${ROOT_DIR}"

echo ""
LOG_SCRIPT="${SCRIPT_DIR}/../cli/print_log.sh"
if [ -f "$LOG_SCRIPT" ]; then
    bash "$LOG_SCRIPT" "SUCCESS" "Commit finished."
else
    echo -e "${GREEN}Success! Commit finished.${RESET}"
fi
