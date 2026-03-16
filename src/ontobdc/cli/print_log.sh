#!/bin/bash

# Define colors
RESET='\033[0m'
BOLD='\033[1m'
GRAY='\033[90m'
WHITE='\033[37m'
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
CYAN='\033[36m'

# Get timestamp
get_timestamp() {
    date "+%H:%M:%S.%3N"
}

# Log function
# Usage: log <LEVEL> <MESSAGE> [KEY=VALUE ...]
log() {
    local LEVEL=$(echo "$1" | tr '[:lower:]' '[:upper:]')
    local MESSAGE="$2"
    shift 2

    local TIMESTAMP=$(get_timestamp)
    local LEVEL_COLOR=""
    local LEVEL_ICON=""

    case "$LEVEL" in
        "INFO")
            LEVEL_COLOR="$BLUE"
            LEVEL_ICON="▶"
            ;;
        "WARN"|"WARNING")
            LEVEL="WARNING"
            LEVEL_COLOR="$YELLOW"
            LEVEL_ICON="▶"
            ;;
        "ERROR")
            LEVEL_COLOR="$RED"
            LEVEL_ICON="▶"
            ;;
        "DEBUG")
            LEVEL_COLOR="$CYAN"
            LEVEL_ICON="▶"
            ;;
        "SUCCESS")
            LEVEL_COLOR="$GREEN"
            LEVEL_ICON="✔"
            ;;
        *)
            LEVEL_COLOR="$WHITE"
            LEVEL_ICON="•"
            ;;
    esac

    # Format: [TIMESTAMP] ICON LEVEL MESSAGE key=value...
    # Example: [19:39:35.583] ▶ INFO Server is running...

    # Print timestamp in gray
    local TIMESTAMP=$(date "+%H:%M:%S")
    echo -ne "${GRAY}[${TIMESTAMP}]${RESET} "
    
    # Print Icon and Level
    echo -ne "${LEVEL_COLOR}${LEVEL_ICON} ${LEVEL}${RESET} "
    
    # Print Message in white
    echo -ne "${WHITE}${MESSAGE}${RESET}"
    
    # Process remaining arguments as key=value pairs
    for pair in "$@"; do
        if [[ "$pair" == *"="* ]]; then
             # Split pair by first =
             local KEY="${pair%%=*}"
             local VAL="${pair#*=}"
             echo -ne " ${BLUE}${KEY}${RESET}=${GRAY}${VAL}${RESET}"
        else
             # Just append as extra text if no =
             echo -ne " ${WHITE}${pair}${RESET}"
        fi
    done

    echo ""
}

# Wrapper function to call log from CLI arguments
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ "$#" -ge 2 ]; then
        log "$@"
    else
        echo "Usage: $0 <LEVEL> <MESSAGE> [KEY=VALUE ...]"
    fi
fi
