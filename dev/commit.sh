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
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TERM_WIDTH=$(tput cols)
INNER_WIDTH=$((TERM_WIDTH - 2))

# Generate horizontal lines
HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))
FULL_HLINE=$(printf '─%.0s' $(seq 1 $TERM_WIDTH))

# --- Functions ---
print_message_box() {
    local COLOR="$1"
    local TITLE_TYPE="$2"    # e.g., "Error", "Success", "Warning"
    local TITLE_TEXT="$3"
    local MSG_TEXT="$4"
    
    # Calculate lengths
    # Title line: " >_ TYPE TITLE"
    # " >_ " is 4 chars.
    
    local TYPE_LEN=${#TITLE_TYPE}
    local TEXT_LEN=${#TITLE_TEXT}
    # Visible length = 4 + TYPE_LEN + 1 (space) + TEXT_LEN
    # If TITLE_TEXT is empty, handle gracefully
    
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
    
    # Handle multi-line messages
    echo -e "$MSG_TEXT" | while IFS= read -r line; do
        # Strip ANSI codes for length calculation
        local CLEAN_LINE=$(echo -e "$line" | sed 's/\x1b\[[0-9;]*m//g')
        local MSG_LEN=${#CLEAN_LINE}
        local MSG_PAD_LEN=$((INNER_WIDTH - MSG_LEN))
        if [ $MSG_PAD_LEN -lt 0 ]; then MSG_PAD_LEN=0; fi
        local MSG_PAD=$(printf '%*s' "$MSG_PAD_LEN" "")
        echo -e "${COLOR}│${RESET}${GRAY}${line}${RESET}${MSG_PAD}${COLOR}│${RESET}"
    done
    
    echo -e "${COLOR}╰${HLINE}╯${RESET}"
}

# Script to automate commits across multiple repositories
# Usage: ./commit.sh "Commit message" OR ./commit.sh --auto

MSG="$1"

if [ "$1" == "--auto" ]; then
    # Check if a prompt definition exists
    PROMPT_FILE="./stack/prompts/commit.md"
    
    if [ ! -f "$PROMPT_FILE" ]; then
        echo ""
        print_message_box "$RED" "Error" "Prompt file not found" "Please create $PROMPT_FILE first."
        echo ""
        exit 1
    fi
    
    # Placeholder logic for AI integration
    # In a real scenario with an API key, we would call it here.
    # For now, we inform the user (or the AI Agent) to use the prompt.
    
    echo ""
    print_message_box "$YELLOW" "Info" "Auto-Commit Mode" "Please use an LLM with the prompt in:\n${CYAN}${PROMPT_FILE}${RESET}\n\nWaiting for manual message input or AI execution..."
    echo ""
    
    # If this script is running interactively without an AI agent hooking into it,
    # we can't magically generate the text.
    # However, if an OPENAI_API_KEY was present, we could do:
    # curl ...
    
    echo -e "${GRAY}To proceed manually, run: ${CYAN}./infobim commit ${GRAY}\"Your message\"${RESET}"
    exit 1
fi

if [ -z "$1" ]; then
    echo ""
    print_message_box "$RED" "Error" "Missing commit message" "Usage: ${CYAN}./infobim commit ${GRAY}\"Your commit message here\"${RESET}"
    echo ""
    exit 1
fi

MSG="$1"
ROOT_DIR="$ROOT_DIR"

echo ""
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo -e "${CYAN}Starting commit process...${RESET}"
echo ""
echo -e "${GRAY}Message: ${WHITE}\"$MSG\"${RESET}"
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

git_commit() {
    local DIR="$1"

    if [ -d "$DIR" ]; then
        # Enter directory
        cd "$DIR" || { echo -e "${RED}Failed to enter $DIR${RESET}"; return; }

        # Check if it is a git repository
        if [ -d ".git" ] || git rev-parse --git-dir > /dev/null 2>&1; then
            BRANCH=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)
            echo -e "${YELLOW}❯ ${WHITE}Processing ${CYAN}${DIR}${RESET} ${GRAY}(${BRANCH})${RESET}"

            # Add changes
            git add .

            # Check if there is anything to commit
            if ! git diff-index --quiet HEAD --; then
                git commit -m "$MSG" > /dev/null 2>&1
                echo -e "  ${GREEN}✓ Committed changes${RESET}"

                # Check if remote exists
                if [ -n "$(git remote)" ]; then
                    git push > /dev/null 2>&1
                    if [ $? -eq 0 ]; then
                        echo -e "  ${GREEN}✓ Pushed to remote${RESET}"
                    else
                        git push --set-upstream origin "$BRANCH" > /dev/null 2>&1
                        if [ $? -eq 0 ]; then
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
        fi
        
        # Return to root directory
        cd "$ROOT_DIR" || return
    fi
}

cd "$ROOT_DIR" || exit 1

while read -r line; do
    git_commit "$line"
done < <(git submodule foreach --recursive 'echo $path')

git_commit "."

echo ""
print_message_box "$GREEN" "Success!" "Commit finished" "All repositories updated."
echo ""
