#!/bin/bash

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
YELLOW='\033[33m'
GREEN='\033[32m'
RED='\033[31m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Determine Root Directory ---
# The script can run in two modes:
# 1. Dev Mode (from source): Script is deep inside core/src/ontobdc/dev
# 2. Installed Mode (pip): Script is inside site-packages/ontobdc/dev

# Try to find the root by looking for .git or .gitmodules upwards from CWD
# This allows 'ontobdc branch' to work from anywhere within a repo
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

# Get terminal width
TERM_WIDTH=$(tput cols)
INNER_WIDTH=$((TERM_WIDTH - 2))

HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))
FULL_HLINE=$(printf '─%.0s' $(seq 1 $TERM_WIDTH))

# --- Functions ---
print_message_box() {
    local COLOR="$1"
    local TITLE_TYPE="$2"    # e.g., "Error", "Success", "Warning"
    local TITLE_TEXT="$3"
    local MSG_TEXT="$4"
    
    local TYPE_LEN=${#TITLE_TYPE}
    local TEXT_LEN=${#TITLE_TEXT}
    
    local TITLE_VISIBLE_LEN=$((4 + TYPE_LEN))
    if [ -n "$TITLE_TEXT" ]; then
        TITLE_VISIBLE_LEN=$((TITLE_VISIBLE_LEN + 1 + TEXT_LEN))
    fi

    local TITLE_PAD_LEN=$((INNER_WIDTH - TITLE_VISIBLE_LEN))
    if [ $TITLE_PAD_LEN -lt 0 ]; then TITLE_PAD_LEN=0; fi
    local TITLE_PAD=$(printf '%*s' "$TITLE_PAD_LEN" "")
    
    local MSG_LEN=${#MSG_TEXT}
    local MSG_PAD_LEN=$((INNER_WIDTH - MSG_LEN))
    if [ $MSG_PAD_LEN -lt 0 ]; then MSG_PAD_LEN=0; fi
    local MSG_PAD=$(printf '%*s' "$MSG_PAD_LEN" "")
    
    local EMPTY_PAD=$(printf '%*s' "$INNER_WIDTH" "")
    
    echo -e "${COLOR}╭${HLINE}╮${RESET}"
    if [ -n "$TITLE_TEXT" ]; then
        echo -e "${COLOR}│${RESET} >_ ${BOLD}${COLOR}${TITLE_TYPE}${RESET} ${TITLE_TEXT}${TITLE_PAD}${COLOR}│${RESET}"
    else
        echo -e "${COLOR}│${RESET} >_ ${BOLD}${COLOR}${TITLE_TYPE}${RESET}${TITLE_PAD}${COLOR}│${RESET}"
    fi
    echo -e "${COLOR}│${RESET}${EMPTY_PAD}${COLOR}│${RESET}"
    echo -e "${COLOR}│${RESET}${GRAY}${MSG_TEXT}${RESET}${MSG_PAD}${COLOR}│${RESET}"
    echo -e "${COLOR}╰${HLINE}╯${RESET}"
}

MODE="status"
BRANCH_NAME=""
TARGET_REF=""

if [ "$#" -gt 0 ]; then
    if [ "$1" = "--create" ]; then
        MODE="create"
        BRANCH_NAME="$2"
        shift 2
    elif [ "$1" = "--checkout" ]; then
        MODE="checkout"
        BRANCH_NAME="$2"
        shift 2
    elif [ "$1" = "--changelog" ]; then
        MODE="changelog"
        if [ "$#" -ge 2 ] && [ -n "${2:-}" ] && [[ "${2:-}" != --* ]]; then
            TARGET_REF="$2"
            shift 2
        else
            shift 1
        fi
    else
        echo ""
        print_message_box "$RED" "Error" "Invalid arguments" "Usage:\n  ontobdc dev branch\n  ontobdc dev branch --create <branch_name>"
        echo ""
        exit 1
    fi
fi

if [ "$MODE" = "create" ] || [ "$MODE" = "checkout" ]; then
    if [ -z "$BRANCH_NAME" ]; then
        echo ""
        print_message_box "$RED" "Error" "Missing branch name" "Usage:\n  ontobdc dev branch --create <branch_name>"
        echo ""
        exit 1
    fi
fi

if [ "$#" -gt 0 ]; then
    echo ""
    print_message_box "$RED" "Error" "Too many arguments" "Usage:\n  ontobdc dev branch\n  ontobdc dev branch --create <branch_name>"
    echo ""
    exit 1
fi

cd "$ROOT_DIR" || exit 1

echo ""
echo -e "${GRAY}${FULL_HLINE}${RESET}"
if [ "$MODE" = "status" ]; then
    echo -e "${CYAN}Listing repositories...${RESET}"
elif [ "$MODE" = "create" ]; then
    echo -e "${CYAN}Creating branch...${RESET}"
    echo -e "${GRAY}Branch: ${WHITE}$BRANCH_NAME${RESET}"
elif [ "$MODE" = "checkout" ]; then
    echo -e "${CYAN}Checking out branch...${RESET}"
    echo -e "${GRAY}Branch: ${WHITE}$BRANCH_NAME${RESET}"
elif [ "$MODE" = "changelog" ]; then
    echo -e "${CYAN}Generating changelog...${RESET}"
    if [ -n "$TARGET_REF" ]; then
        echo -e "${GRAY}Target: ${WHITE}$TARGET_REF${RESET}"
    fi
fi
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

repo_status() {
    local DIR="$1"

    if [ -d "$DIR" ]; then
        (
            cd "$DIR" || exit 0
            if ! git rev-parse --git-dir > /dev/null 2>&1; then
                exit 0
            fi

            local REPO_NAME
            REPO_NAME=$(basename "$DIR")
            local BRANCH
            BRANCH=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

            echo ""
            echo -e "${YELLOW}❯ ${WHITE}${REPO_NAME} ${CYAN}(${BRANCH})${RESET}"

            local STATUS
            STATUS=$(git status --porcelain=v1 2>/dev/null)
            if [ -z "$STATUS" ]; then
                echo -e "  ${GRAY}• clean${RESET}"
            else
                while IFS= read -r line; do
                    [ -z "$line" ] && continue
                    local code="${line:0:2}"
                    local path="${line:3}"
                    if [ "$DIR" = "$ROOT_DIR" ]; then
                        for sub in $SUBMODULES ontobdc-wip ontobdc-core core wip; do
                            if [ -n "$sub" ] && [ "$path" = "$sub" ]; then
                                continue 2
                            fi
                        done
                    fi
                    local color="$WHITE"
                    local label="modified"
                    if [[ "$code" == "??" ]]; then
                        color="$CYAN"
                        label="untracked"
                    elif [[ "$code" == *"A"* ]]; then
                        color="$GREEN"
                        label="added"
                    elif [[ "$code" == *"M"* ]]; then
                        color="$YELLOW"
                        label="modified"
                    elif [[ "$code" == *"D"* ]]; then
                        color="$RED"
                        label="deleted"
                    fi
                    echo -e "  ${color}[${label}]${RESET} ${GRAY}${path}${RESET}"
                done <<< "$STATUS"
            fi
        )
    fi
}

git_branch() {
    local DIR="$1"
    (
        cd "$DIR" || exit 0
        if ! git rev-parse --git-dir > /dev/null 2>&1; then
            exit 0
        fi

        local REPO_NAME
        REPO_NAME=$(basename "$DIR")
        echo -e "${YELLOW}❯ ${WHITE}Processing ${CYAN}${REPO_NAME}${RESET}"

        if [ "$MODE" = "create" ]; then
            if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
                echo -e "  ${YELLOW}! Branch '$BRANCH_NAME' already exists${RESET}"
            else
                git checkout -b "$BRANCH_NAME" > /dev/null 2>&1
                echo -e "  ${GREEN}✓ Created local branch${RESET}"
                if [ -n "$(git remote)" ]; then
                    git push --set-upstream origin "$BRANCH_NAME" > /dev/null 2>&1
                    if [ $? -eq 0 ]; then
                        echo -e "  ${GREEN}✓ Pushed upstream${RESET}"
                    else
                        echo -e "  ${RED}✗ Failed to push upstream${RESET}"
                    fi
                fi
            fi
        elif [ "$MODE" = "checkout" ]; then
            if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME" || \
               git show-ref --verify --quiet "refs/remotes/origin/$BRANCH_NAME"; then
                CHECKOUT_OUTPUT=$(git checkout "$BRANCH_NAME" 2>&1)
                if [ $? -eq 0 ]; then
                    echo -e "  ${GREEN}✓ Checked out${RESET}"
                else
                    echo -e "  ${RED}✗ Checkout failed${RESET}"
                    if [ -n "$CHECKOUT_OUTPUT" ]; then
                        while IFS= read -r l; do
                            [ -n "$l" ] && echo -e "  ${GRAY}${l}${RESET}"
                        done <<< "$CHECKOUT_OUTPUT"
                    fi
                fi
            else
                echo -e "  ${YELLOW}! Warning: Branch '$BRANCH_NAME' does not exist in this repo${RESET}"
            fi
        elif [ "$MODE" = "changelog" ]; then
            local BASE_BRANCH=""

            if [ -n "$TARGET_REF" ]; then
                if git show-ref --verify --quiet "refs/remotes/origin/$TARGET_REF"; then
                    BASE_BRANCH="origin/$TARGET_REF"
                elif git show-ref --verify --quiet "refs/heads/$TARGET_REF"; then
                    BASE_BRANCH="$TARGET_REF"
                else
                    echo -e "  ${YELLOW}! Warning: Target branch '$TARGET_REF' not found. Falling back to defaults.${RESET}"
                fi
            fi

            if [ -z "$BASE_BRANCH" ]; then
                if git show-ref --verify --quiet "refs/remotes/origin/develop"; then
                    BASE_BRANCH="origin/develop"
                elif git show-ref --verify --quiet "refs/heads/develop"; then
                    BASE_BRANCH="develop"
                fi
            fi

            if [ -z "$BASE_BRANCH" ]; then
                if git show-ref --verify --quiet "refs/remotes/origin/main"; then
                    BASE_BRANCH="origin/main"
                elif git show-ref --verify --quiet "refs/remotes/origin/master"; then
                    BASE_BRANCH="origin/master"
                elif git show-ref --verify --quiet "refs/heads/main"; then
                    BASE_BRANCH="main"
                elif git show-ref --verify --quiet "refs/heads/master"; then
                    BASE_BRANCH="master"
                fi
            fi

            if [ -n "$BASE_BRANCH" ]; then
                local CURRENT_BRANCH
                CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
                echo -e "  ${GRAY}Comparing ${WHITE}$CURRENT_BRANCH${GRAY} with ${WHITE}$BASE_BRANCH${RESET}"
                local MERGE_BASE
                MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null)
                if [ -n "$MERGE_BASE" ]; then
                    local CHANGES
                    CHANGES=$(git diff --name-status "$MERGE_BASE"..HEAD)
                    if [ -z "$CHANGES" ]; then
                        echo -e "  ${GRAY}No changes detected since split from $BASE_BRANCH${RESET}"
                    else
                        echo -e "  ${WHITE}Changes since split from $BASE_BRANCH:${RESET}"
                        echo "$CHANGES" | while read -r status file; do
                            if [[ "$status" == "A"* ]]; then
                                echo -e "    ${GREEN}[+] $file${RESET}"
                            elif [[ "$status" == "M"* ]]; then
                                echo -e "    ${YELLOW}[~] $file${RESET}"
                            elif [[ "$status" == "D"* ]]; then
                                echo -e "    ${RED}[-] $file${RESET}"
                            else
                                echo -e "    ${GRAY}[$status] $file${RESET}"
                            fi
                        done
                    fi
                else
                    echo -e "  ${YELLOW}! Could not find merge base with $BASE_BRANCH${RESET}"
                fi
            else
                echo -e "  ${YELLOW}! Could not determine base branch (main/master)${RESET}"
            fi
        fi
    )
}

process_repo() {
    local REPO_PATH="$1"
    local REPO_NAME=$(basename "$REPO_PATH")
    
    # Skip if directory doesn't exist
    if [ ! -d "$REPO_PATH" ]; then
        return
    fi
    
    # Check if it's a git repo
    # Check for .git dir or .git file (submodules)
    if [ ! -d "$REPO_PATH/.git" ] && [ ! -f "$REPO_PATH/.git" ]; then
        return
    fi

    if [ "$MODE" = "status" ]; then
        repo_status "$REPO_PATH"
    else
        echo -e "${YELLOW}❯ Processing ${REPO_NAME}${RESET}"
        git_branch "$REPO_PATH"
    fi
}

# 1. Process Submodules explicitly detected via .gitmodules
if [ -f "${ROOT_DIR}/.gitmodules" ]; then
    # Extract paths from .gitmodules
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

# 4. Process core explicitly (new structure)
if [ -d "${ROOT_DIR}/core" ]; then
    if [[ "$SUBMODULES" != *"core"* ]]; then
        process_repo "${ROOT_DIR}/core"
    fi
fi

# 5. Process wip explicitly (new structure)
if [ -d "${ROOT_DIR}/wip" ]; then
    if [[ "$SUBMODULES" != *"wip"* ]]; then
        process_repo "${ROOT_DIR}/wip"
    fi
fi

# 4. Process Root Repository (Last)
# Note: git_branch handles entering the dir.
# But git_branch expects the dir path.
if [ "$MODE" = "status" ]; then
    repo_status "${ROOT_DIR}"
else
    echo -e "${YELLOW}❯ Processing Root${RESET}"
    git_branch "${ROOT_DIR}"
fi

echo ""
if [ "$MODE" != "status" ]; then
    print_message_box "$GREEN" "Success!" "Branch process finished" "All repositories processed."
fi
echo ""
