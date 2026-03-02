#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# When installed via pip, the structure is flat inside site-packages/ontobdc/cli
# SCRIPT_DIR is .../ontobdc/cli
# MODULE_ROOT is .../ontobdc
MODULE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Try to find message_box.sh in likely locations
# 1. In project root (development mode): .../src/ontobdc/cli/../../message_box.sh -> src/../message_box.sh (ontobdc-wip/message_box.sh)
# 2. In installed package root: .../site-packages/ontobdc/message_box.sh

if [ -f "${MODULE_ROOT}/../../message_box.sh" ]; then
    MESSAGE_BOX="${MODULE_ROOT}/../../message_box.sh"
elif [ -f "${MODULE_ROOT}/message_box.sh" ]; then
    MESSAGE_BOX="${MODULE_ROOT}/message_box.sh"
else
    MESSAGE_BOX="${MODULE_ROOT}/message_box.sh"
fi

# Define paths
# Note: config.json is in check/config.json relative to module root
CONFIG_JSON="${MODULE_ROOT}/check/config.json"

if [ -f "${MESSAGE_BOX}" ]; then
    source "${MESSAGE_BOX}"
else
    # Fallback if message_box is missing
    echo "Warning: message_box.sh not found at ${MESSAGE_BOX}"
    print_message_box() {
        echo "[$1] $2: $3"
        echo -e "$4"
    }
    # Define colors if not sourced
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    GRAY='\033[0;90m'
    WHITE='\033[1;37m'
    RESET='\033[0m'
fi

# Function to display usage
usage() {
    echo -e "Usage: ontobdc setup <engine>"
    echo -e "Available engines can be found in config.json"
}

# Check argument
if [ -z "$1" ]; then
    usage
    exit 1
fi

ENGINE_ARG="$1"

# Validate engine
if [ ! -f "$CONFIG_JSON" ]; then
    echo -e "${RED}Error: Config file not found at ${CONFIG_JSON}${RESET}"
    exit 1
fi

IS_VALID=$(python3 -c "import json; import sys; 
try:
    with open('$CONFIG_JSON') as f: data = json.load(f);
    engines = data.get('config', {}).get('engines', [])
    if '$ENGINE_ARG' in engines: print('true')
    else: print('false')
except Exception as e: print('false')")

if [ "$IS_VALID" != "true" ]; then
    echo -e "${RED}Error: Invalid engine '$ENGINE_ARG'.${RESET}"
    echo -e "Valid engines are defined in check/config.json."
    exit 1
fi

# Determine config file path
# If in Colab (/content exists), use /content/config/ontobdc.yaml
# Otherwise use local config/ontobdc.yaml relative to where command is run?
# Or relative to project root?
# Let's assume:
# If /content exists -> /content/config/ontobdc.yaml
# Else -> ./config/ontobdc.yaml (relative to CWD)

if [ -d "/content" ]; then
    CONFIG_DIR="/content/config"
    CONFIG_FILE="${CONFIG_DIR}/ontobdc.yaml"
else
    # Use current directory's config folder if we are in project root
    # Or try to find project root?
    # Let's default to ./config/ontobdc.yaml for local usage
    CONFIG_DIR="config"
    CONFIG_FILE="${CONFIG_DIR}/ontobdc.yaml"
fi

# Create directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo -e "${GRAY}Creating directory ${CONFIG_DIR}...${RESET}"
    mkdir -p "$CONFIG_DIR"
fi

# Create or update config file
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${GRAY}Updating existing config file at ${CONFIG_FILE}...${RESET}"
    # Remove existing engine definition if any
    grep -v "engine:" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
else
    echo -e "${GRAY}Creating new config file at ${CONFIG_FILE}...${RESET}"
    touch "$CONFIG_FILE"
fi

# Append new engine
echo "engine: $ENGINE_ARG" >> "$CONFIG_FILE"

echo -e "${GREEN}Success: Engine set to '$ENGINE_ARG' in ${CONFIG_FILE}${RESET}"

# Run check --repair
echo ""
echo -e "${CYAN}Running system check and repair...${RESET}"

# Try to find check.sh relative to this script
CHECK_SCRIPT="${MODULE_ROOT}/check/check.sh"

if [ -f "$CHECK_SCRIPT" ]; then
    bash "$CHECK_SCRIPT" --repair
else
    # Fallback to calling ontobdc check via CLI if available in path
    if command -v ontobdc &> /dev/null; then
        ontobdc check --repair
    else
        echo -e "${RED}Error: check.sh not found at ${CHECK_SCRIPT} and ontobdc command not in PATH.${RESET}"
        exit 1
    fi
fi

exit 0
