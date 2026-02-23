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
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

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

# Script to automate branch creation and checkout
# Usage: ./branch.sh <action> <branch_name>
# Actions: create, checkout

if [ -z "$1" ]; then
    echo ""
    print_message_box "$RED" "Error" "Missing arguments" "Usage: $0 <create|checkout|changelog> [branch_name]"
    echo ""
    exit 1
fi

ACTION="$1"
BRANCH_NAME="$2"

# Validation for create/checkout
if [[ "$ACTION" == "create" || "$ACTION" == "checkout" ]]; then
    if [ -z "$BRANCH_NAME" ]; then
         echo ""
         print_message_box "$RED" "Error" "Missing branch name" "Usage: $0 $ACTION <branch_name>"
         echo ""
         exit 1
    fi
fi

cd "$ROOT_DIR" || exit 1

echo ""
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo -e "${CYAN}Starting branch $ACTION...${RESET}"
if [ -n "$BRANCH_NAME" ]; then
    echo -e "${GRAY}Branch: ${WHITE}$BRANCH_NAME${RESET}"
fi
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

git_branch() {
    local DIR="$1"

    if [ -d "$DIR" ]; then
        cd "$DIR" || { echo -e "${RED}Failed to enter $DIR${RESET}"; return; }

        # Check if it is a git repository
        if [ -d ".git" ] || git rev-parse --git-dir > /dev/null 2>&1; then
            echo -e "${YELLOW}❯ ${WHITE}Processing ${CYAN}${DIR}${RESET}"
            
            if [ "$ACTION" == "create" ]; then
                # Create branch (checks if it already exists to avoid error)
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
            elif [ "$ACTION" == "checkout" ]; then
                # Checkout branch
                # Check if branch exists (local or remote)
                if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME" || \
                   git show-ref --verify --quiet "refs/remotes/origin/$BRANCH_NAME"; then
                    
                    git checkout "$BRANCH_NAME" > /dev/null 2>&1
                    if [ $? -eq 0 ]; then
                        echo -e "  ${GREEN}✓ Checked out${RESET}"
                    else
                        echo -e "  ${RED}✗ Checkout failed${RESET}"
                    fi
                else
                    echo -e "  ${YELLOW}! Warning: Branch '$BRANCH_NAME' does not exist in this repo${RESET}"
                fi
            elif [ "$ACTION" == "changelog" ]; then
                # Changelog: List added, modified, removed files since branch start
                # Usage: ./infobim branch changelog [target_branch]
                
                TARGET_REF="$BRANCH_NAME"
                BASE_BRANCH=""

                # 1. Try provided target branch
                if [ -n "$TARGET_REF" ]; then
                    if git show-ref --verify --quiet "refs/remotes/origin/$TARGET_REF"; then
                        BASE_BRANCH="origin/$TARGET_REF"
                    elif git show-ref --verify --quiet "refs/heads/$TARGET_REF"; then
                        BASE_BRANCH="$TARGET_REF"
                    else
                         echo -e "  ${YELLOW}! Warning: Target branch '$TARGET_REF' not found. Falling back to defaults.${RESET}"
                    fi
                fi

                # 2. Try default 'develop' if no base found yet
                if [ -z "$BASE_BRANCH" ]; then
                    if git show-ref --verify --quiet "refs/remotes/origin/develop"; then
                        BASE_BRANCH="origin/develop"
                    elif git show-ref --verify --quiet "refs/heads/develop"; then
                        BASE_BRANCH="develop"
                    fi
                fi

                # 3. Fallback to main/master if still no base found
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
                    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
                    echo -e "  ${GRAY}Comparing ${WHITE}$CURRENT_BRANCH${GRAY} with ${WHITE}$BASE_BRANCH${RESET}"
                    
                    MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null)
                    if [ -n "$MERGE_BASE" ]; then
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
            else
                echo -e "  ${RED}Invalid action: $ACTION. Use 'create', 'checkout', or 'changelog'.${RESET}"
            fi
        fi
        
        # Return to root directory
        cd "$ROOT_DIR" || return
    fi
}

# Process sub-repositories (like infra) found by find command
# This covers both submodules (if initialized) and manual sub-repos
find . -maxdepth 2 -name ".git" | while read git_dir; do
    repo_dir=$(dirname "$git_dir")
    # Skip current directory (.) to avoid double processing (it's handled at the end)
    if [ "$repo_dir" != "." ] && [ "$repo_dir" != "./." ]; then
        # Remove ./ prefix if present for cleaner output
        clean_dir=${repo_dir#./}
        git_branch "$clean_dir"
    fi
done

# Process root repository
git_branch "."

echo ""
print_message_box "$GREEN" "Success!" "Branch process finished" "All repositories processed."
echo ""
