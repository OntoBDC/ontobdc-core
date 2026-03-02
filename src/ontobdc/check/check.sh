#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# When installed via pip, the structure is flat inside site-packages/ontobdc
# SCRIPT_DIR is .../ontobdc/check
# MODULE_ROOT is .../ontobdc
MODULE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Try to find message_box.sh in likely locations
# 1. In project root (development mode): .../src/ontobdc/../../message_box.sh -> src/../message_box.sh (ontobdc-wip/message_box.sh)
# 2. In installed package root: .../site-packages/ontobdc/message_box.sh

# Check if we are in development mode (source tree)
if [ -f "${MODULE_ROOT}/../../message_box.sh" ]; then
    MESSAGE_BOX="${MODULE_ROOT}/../../message_box.sh"
elif [ -f "${MODULE_ROOT}/message_box.sh" ]; then
    # Installed package mode, or flat structure
    MESSAGE_BOX="${MODULE_ROOT}/message_box.sh"
else
    # Fallback/Unknown
    MESSAGE_BOX="${MODULE_ROOT}/message_box.sh"
fi

# Define paths
CONFIG_JSON="${SCRIPT_DIR}/config.json"

if [ -f "${MESSAGE_BOX}" ]; then
    source "${MESSAGE_BOX}"
else
    # Fallback if message_box is missing
    # echo "Warning: message_box.sh not found at ${MESSAGE_BOX}"
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
    FULL_HLINE="----------------------------------------"
fi

REPAIR_MODE=false
SCOPE="all"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --repair) REPAIR_MODE=true ;;
        --scope) SCOPE="$2"; shift ;;
        *) ;;
    esac
    shift
done

echo ""
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo -e "${CYAN}Running System Checks...${RESET}"
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

ERRORS=()
WARNINGS=()

run_checks() {
    local DIR="$1"
    local NAME="$2"
    local ENGINE="$3"
    
    echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}${NAME}${RESET}"
    
    if [ ! -f "$CONFIG_JSON" ]; then
         echo -e "  ${RED}✗ Config file not found: ${CONFIG_JSON}${RESET}"
         ERRORS+=("Config file missing")
         return
    fi

    # Parse JSON using python
    # Get base checks
    BASE_CHECKS=$(python3 -c "import json; import sys; 
try:
    with open('$CONFIG_JSON') as f: data = json.load(f);
    print(' '.join(data.get('base', {}).get('$NAME', [])))
except Exception as e: print(e, file=sys.stderr)")

    # Get engine specific checks
    ENGINE_CHECKS=$(python3 -c "import json; import sys; 
try:
    with open('$CONFIG_JSON') as f: data = json.load(f);
    print(' '.join(data.get('engines', {}).get('$ENGINE', {}).get('$NAME', [])))
except Exception as e: print(e, file=sys.stderr)")

    CHECKS="$BASE_CHECKS $ENGINE_CHECKS"
    
    if [ -z "$CHECKS" ] || [ "$CHECKS" == " " ]; then
        echo -e "  ${GRAY}• No checks found for $NAME in $ENGINE${RESET}"
        return
    fi

    for check_name in $CHECKS; do
        # Check script path: dir/check_name/init.sh
        check_script="$DIR/$check_name/init.sh"
        
        if [ -f "$check_script" ]; then
            DESCRIPTION=""
            unset -f check
            unset -f repair
            unset -f hotfix
            
            # shellcheck disable=SC1090
            source "$check_script"
            
            # Default description if missing
            if [ -z "$DESCRIPTION" ]; then
                DESCRIPTION="$check_name"
            fi

            check
            RET_CODE=$?

            if [ $RET_CODE -eq 0 ]; then
                 echo -e "  ${GREEN}✓ ${DESCRIPTION}${RESET}"
            else
                 # If return code is 2, it's a fatal error that requires immediate attention (and potentially abort via repair)
                 IS_FATAL=false
                 if [ $RET_CODE -eq 2 ]; then
                    IS_FATAL=true
                 fi

                 HOTFIXED=false
                 if type hotfix &>/dev/null; then
                     if hotfix; then
                         if check; then
                             echo -e "  ${GREEN}✓ ${DESCRIPTION} (Hotfixed)${RESET}"
                             WARNINGS+=("${DESCRIPTION} (Hotfixed)")
                             HOTFIXED=true
                         fi
                     fi
                 fi

                 if [ "$HOTFIXED" = false ]; then
                     # If fatal error, force repair attempt immediately regardless of --repair flag
                     # Or simply fail hard if repair() calls exit 1
                     if [ "$IS_FATAL" = true ]; then
                         echo -e "  ${RED}✗ ${DESCRIPTION} (FATAL)${RESET}"
                         if type repair &>/dev/null; then
                             repair # This is expected to exit 1 if it can't fix
                         else
                             echo -e "${RED}FATAL ERROR: ${DESCRIPTION} failed and no repair available.${RESET}"
                             exit 1
                         fi
                     fi

                     if [ "$REPAIR_MODE" = true ]; then
                         echo -e "  ${YELLOW}⚡ Attempting repair for: ${DESCRIPTION}...${RESET}"
                         if type repair &>/dev/null; then
                             repair
                             
                             check
                             if [ $? -eq 0 ]; then
                                 echo -e "  ${GREEN}✓ ${DESCRIPTION} (Repaired)${RESET}"
                                 WARNINGS+=("${DESCRIPTION} (Repaired)")
                             else
                                 echo -e "  ${RED}✗ ${DESCRIPTION} (Repair failed)${RESET}"
                                 ERRORS+=("${DESCRIPTION}")
                             fi
                         else
                             echo -e "  ${RED}✗ ${DESCRIPTION} (No repair function)${RESET}"
                             ERRORS+=("${DESCRIPTION}")
                         fi
                     else
                         echo -e "  ${RED}✗ ${DESCRIPTION}${RESET}"
                         ERRORS+=("${DESCRIPTION}")
                     fi
                 fi
            fi
        else
             echo -e "  ${GRAY}• Check script not found: $check_script${RESET}"
        fi
    done
}

# Determine Engine
ENGINE="venv"
# Heuristic for colab
if [ -d "/content" ]; then
    ENGINE="colab"
fi

if [[ "$SCOPE" == "all" || "$SCOPE" == "infra" ]]; then
    # Correct path to infra checks
    # If SCRIPT_DIR is .../ontobdc/check, infra is SCRIPT_DIR/infra
    INFRA_DIR="${SCRIPT_DIR}/infra"
    
    if [[ -d "${INFRA_DIR}" ]]; then
        run_checks "${INFRA_DIR}" "infra" "$ENGINE"
    else
        # Try finding it relative to module root if we are in a weird symlink situation?
        # Or maybe it's missing in installation
        echo -e "${RED}Error: Infra checks directory not found at ${INFRA_DIR}${RESET}"
    fi
fi

if [ -z "$VIRTUAL_ENV" ] && [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "venv/bin/activate"
fi

echo ""

if [ ${#ERRORS[@]} -eq 0 ]; then
    MSG="All checks passed."
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        MSG="${MSG}\n\nWarnings:"
        for w in "${WARNINGS[@]}"; do
            MSG="${MSG}\n• $w"
        done
    fi
    if type print_message_box &>/dev/null; then
        print_message_box "$GREEN" "Success" "System Operational" "$MSG"
    else
        echo -e "${GREEN}Success: System Operational${RESET}\n$MSG"
    fi
else
    MSG="The following checks failed:"
    for e in "${ERRORS[@]}"; do
        MSG="${MSG}\n• $e"
    done
    
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        MSG="${MSG}\n\nWarnings:"
        for w in "${WARNINGS[@]}"; do
            MSG="${MSG}\n• $w"
        done
    fi
    
    if type print_message_box &>/dev/null; then
        print_message_box "$RED" "Error" "System Check Failed" "$MSG"
    else
        echo -e "${RED}Error: System Check Failed${RESET}\n$MSG"
    fi
    # Exit with error code if there were errors
    exit 1
fi

echo ""
exit 0
