#!/bin/bash

BOLD='\033[1m'
RESET='\033[0m'
CYAN='\033[36m'
GRAY='\033[90m'
WHITE='\033[37m'
BLUE='\033[34m'
RED='\033[31m'

SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -h "$SCRIPT_PATH" ]; do
    DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    TARGET="$(readlink "$SCRIPT_PATH")"
    case "$TARGET" in
        /*) SCRIPT_PATH="$TARGET" ;;
        *) SCRIPT_PATH="$DIR/$TARGET" ;;
    esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/ontobdc.yaml"

if [[ "$1" == "commit" || "$1" == "branch" ]]; then
    ACTION="$1"
    TOOL_SCRIPT="${SCRIPT_DIR}/dev/${ACTION}.sh"

    if [[ -f "$TOOL_SCRIPT" ]]; then
        shift
        bash "$TOOL_SCRIPT" "$@"
        exit $?
    else
        echo -e "${RED}Error:${RESET} ${ACTION}.sh not found in ontobdc/dev"
        exit 1
    fi
fi

if [[ "$1" == "run" || "$1" == "plan" ]]; then
    ACTION="$1"
    TOOL_SCRIPT="${SCRIPT_DIR}/run/${ACTION}.sh"

    if [[ -f "$TOOL_SCRIPT" ]]; then
        shift
        bash "$TOOL_SCRIPT" "$@"
        exit $?
    else
        echo -e "${RED}Error:${RESET} ${ACTION}.sh not found in ontobdc/run"
        exit 1
    fi
fi

if [[ -z "$1" || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]]; then
    echo -e "${WHITE}ontobdc CLI${RESET}"
    echo -e "  ${CYAN}commit${RESET}    ${GRAY}Git workflow for ontobdc and related modules${RESET}"
    echo -e "  ${CYAN}branch${RESET}    ${GRAY}Branch workflow for ontobdc and related modules${RESET}"
    echo -e "  ${CYAN}run${RESET}       ${GRAY}Run a capability via ontobdc/run${RESET}"
    echo -e "  ${CYAN}plan${RESET}      ${GRAY}Plan capability execution${RESET}"
    exit 0
fi

echo -e "${RED}Error:${RESET} unknown command '${1}'."
echo -e "${GRAY}Use ./ontobdc.sh -h for available commands.${RESET}"
exit 1
