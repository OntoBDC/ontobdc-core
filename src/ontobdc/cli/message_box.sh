#!/bin/bash

# Define colors
BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
YELLOW='\033[33m'
GREEN='\033[32m'
RED='\033[31m'
BLUE='\033[34m'

# Get terminal width
TERM_WIDTH=$(tput cols)
INNER_WIDTH=$((TERM_WIDTH - 2))

# Generate horizontal lines
HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))

print_message_box() {
    local COLOR="$1"
    local TITLE_TYPE="$2"    # e.g., "Error", "Success", "Warning"
    local TITLE_TEXT="$3"
    local MSG_TEXT="$4"
    local SUBTITLE_TEXT="$5"
    local FOOTER_TEXT="$6"

    # Use full terminal width
    local TERM_COLS=$(tput cols)
    local INNER_WIDTH=$((TERM_COLS - 2))
    local HLINE=$(printf '─%.0s' $(seq 1 $INNER_WIDTH))
    
    # Resolve color name to code if passed as string name
    case "$COLOR" in
        "RED") COLOR="$RED" ;;
        "GREEN") COLOR="$GREEN" ;;
        "YELLOW") COLOR="$YELLOW" ;;
        "CYAN") COLOR="$CYAN" ;;
        "BLUE") COLOR="$BLUE" ;;
        "WHITE") COLOR="$WHITE" ;;
        "GRAY") COLOR="$GRAY" ;;
    esac

    local TYPE_LEN=${#TITLE_TYPE}
    local TEXT_LEN=${#TITLE_TEXT}
    
    local TITLE_VISIBLE_LEN=$((4 + TYPE_LEN))
    if [ -n "$TITLE_TEXT" ]; then
        TITLE_VISIBLE_LEN=$((TITLE_VISIBLE_LEN + 1 + TEXT_LEN))
    fi

    local TITLE_PAD_LEN=$((INNER_WIDTH - TITLE_VISIBLE_LEN))
    if [ $TITLE_PAD_LEN -lt 0 ]; then TITLE_PAD_LEN=0; fi
    local TITLE_PAD=$(printf '%*s' "$TITLE_PAD_LEN" "")
    
    local EMPTY_PAD=$(printf '%*s' "$INNER_WIDTH" "")
    
    local TITLE_TYPE_COLOR="$COLOR"
    
    # Force BLUE for "OntoBDC" title type
    if [ "$TITLE_TYPE" == "OntoBDC" ]; then
        TITLE_TYPE_COLOR="$BLUE"
    fi
    
    echo -e "${COLOR}╭${HLINE}╮${RESET}"
    if [ -n "$TITLE_TEXT" ]; then
        echo -e "${COLOR}│${RESET} >_ ${BOLD}${TITLE_TYPE_COLOR}${TITLE_TYPE}${RESET} ${TITLE_TEXT}${TITLE_PAD}${COLOR}│${RESET}"
    else
        echo -e "${COLOR}│${RESET} >_ ${BOLD}${TITLE_TYPE_COLOR}${TITLE_TYPE}${RESET}${TITLE_PAD}${COLOR}│${RESET}"
    fi
    echo -e "${COLOR}│${RESET}${EMPTY_PAD}${COLOR}│${RESET}"

    if [ -n "$SUBTITLE_TEXT" ]; then
        local SUB_LEN=${#SUBTITLE_TEXT}
        local SUB_PAD_LEN=$((INNER_WIDTH - SUB_LEN))
        if [ $SUB_PAD_LEN -lt 0 ]; then SUB_PAD_LEN=0; fi
        local SUB_PAD=$(printf '%*s' "$SUB_PAD_LEN" "")
        echo -e "${COLOR}│${RESET}${GRAY}${SUBTITLE_TEXT}${RESET}${SUB_PAD}${COLOR}│${RESET}"
        echo -e "${COLOR}│${RESET}${EMPTY_PAD}${COLOR}│${RESET}"
    fi
    
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
    
    if [ -n "$FOOTER_TEXT" ]; then
        # Add padding line before footer
        echo -e "${COLOR}│${RESET}${EMPTY_PAD}${COLOR}│${RESET}"
        
        # Custom bottom border with text
        # Format: ╰─ TEXT ─...─╯
        local CLEAN_FOOTER=$(echo -e "$FOOTER_TEXT" | sed 's/\x1b\[[0-9;]*m//g')
        local FOOTER_LEN=${#CLEAN_FOOTER}

        local REMAINING_WIDTH=$((INNER_WIDTH - FOOTER_LEN - 3)) 
        if [ $REMAINING_WIDTH -lt 0 ]; then REMAINING_WIDTH=0; fi
        
        # Left line length: 1 char
        local LEFT_LINE="─"
        local RIGHT_LINE=$(printf '─%.0s' $(seq 1 $REMAINING_WIDTH))
        
        echo -e "${COLOR}╰${LEFT_LINE} ${FOOTER_TEXT} ${COLOR}${RIGHT_LINE}╯${RESET}"
    else
        echo -e "${COLOR}╰${HLINE}╯${RESET}"
    fi
}

# If executed directly with arguments, run the function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ "$#" -ge 4 ]; then
        print_message_box "$1" "$2" "$3" "$4" "$5" "$6"
    fi
fi
