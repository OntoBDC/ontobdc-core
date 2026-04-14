#!/bin/bash

# When installed via pip, the structure is flat inside site-packages/ontobdc
# MODULE_ROOT is .../ontobdc
MODULE_ROOT="$(
    PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd):${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_root_dir; print(get_root_dir())" 2>/dev/null
)"

SCRIPT_DIR="$(
    PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd):${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_script_dir; print(get_script_dir())" 2>/dev/null
)"

ONTOBDC_DIR="${SCRIPT_DIR}"

MESSAGE_BOX="${ONTOBDC_DIR}/cli/message_box.sh"

# Define paths
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
WHITE='\033[1;37m'
RESET='\033[0m'
FULL_HLINE="----------------------------------------"

DEFAULT_CONFIG_JSON="${ONTOBDC_DIR}/check/config.json"

CONFIG_JSON="${MODULE_ROOT}/.__ontobdc__/check.json"
if [ ! -f "${CONFIG_JSON}" ]; then
    CONFIG_JSON="${DEFAULT_CONFIG_JSON}"
fi

CONFIG_VALID=$(python3 -c "import json, sys
p='${CONFIG_JSON}'
try:
    with open(p) as f:
        data = json.load(f) or {}
except Exception:
    print('0')
    sys.exit(0)
base = data.get('base', None)
print('1' if isinstance(base, dict) and len(base) > 0 else '0')" 2>/dev/null)

if [ -f "${MESSAGE_BOX}" ]; then
    source "${MESSAGE_BOX}"
else
    # Fallback if message_box is missing
    # echo "Warning: message_box.sh not found at ${MESSAGE_BOX}"
    print_message_box() {
        echo "[$1] $2: $3"
        echo -e "$4"
    }
fi

if [ -f "${MESSAGE_BOX}" ]; then
    # Define FULL_HLINE if sourced from message_box (if it's not defined there)
    # message_box.sh doesn't define FULL_HLINE, but it defines colors.
    # We should ensure colors are available or redefined here if needed, 
    # but sourcing message_box should provide them.
    # However, message_box.sh defines colors as BOLD='\033[1m', etc.
    # Let's just redefine FULL_HLINE here to be safe.
    FULL_HLINE="----------------------------------------"
fi

REPAIR_MODE=false
SCOPE="all"
COMPACT_MODE=false
ONLY_CHECK=""
IGNORE_WARNINGS=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --repair) REPAIR_MODE=true ;;
        --scope) SCOPE="$2"; shift ;;
        --only) ONLY_CHECK="$2"; shift ;;
        --ignore-warnings) IGNORE_WARNINGS=true ;;
        -c|--compact) COMPACT_MODE=true ;;
        *) ;;
    esac
    shift
done

PRINT_LOG="${ONTOBDC_DIR}/cli/print_log.sh"
log_line() {
    local LEVEL="$1"
    local MESSAGE="$2"
    shift 2
    if [ -f "$PRINT_LOG" ]; then
        bash "$PRINT_LOG" "$LEVEL" "$MESSAGE" "$@"
    else
        echo "$LEVEL: $MESSAGE"
    fi
}

if [ "$COMPACT_MODE" = true ]; then
    log_line "INFO" "Running system checks..."
else
    echo ""
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo -e "${CYAN}Running System Checks...${RESET}"
    echo -e "${GRAY}${FULL_HLINE}${RESET}"
    echo ""
fi

ERRORS=()
WARNINGS=()

ON_FAILURE=$(python3 -c "import json
p='${CONFIG_JSON}'
try:
    with open(p) as f:
        data=json.load(f) or {}
except Exception:
    data={}
base=data.get('base',{}) or {}
beh=(base.get('behavor') or base.get('behavior') or {}) if isinstance(base,dict) else {}
val=(beh.get('on_failure') or 'continue') if isinstance(beh,dict) else 'continue'
print(str(val).strip() or 'continue')" 2>/dev/null)
if [ -z "$ON_FAILURE" ]; then
    ON_FAILURE="continue"
fi

run_checks() {
    local DIR="$1"
    local NAME="$2"
    local ENGINE="$3"

    if [ -z "$ONLY_CHECK" ]; then
        if [ ! -f "$CONFIG_JSON" ]; then
             echo -e "  ${RED}✗ Config file not found: ${CONFIG_JSON}${RESET}"
             ERRORS+=("Config file missing")
             return
        fi
    fi

    CHECKS_DICT=$(python3 -c "import json, os, sys
try:
    with open('$CONFIG_JSON') as f:
        data = json.load(f) or {}
except Exception:
    data = {}
out = {}
base = (data.get('base', {}) or {}).get('$NAME', []) or []
engine = ((data.get('engine', {}) or {}).get('$ENGINE', {}) or {}).get('$NAME', []) or []
if base:
    out['base'] = ' '.join(base)
if engine:
    out['engine'] = ' '.join(engine)

script_path = (data.get('script_path', {}) or {}).get('alternative', None)
candidates = []
if isinstance(script_path, str):
    candidates = [script_path]
elif isinstance(script_path, list):
    candidates = [c for c in script_path if isinstance(c, str)]

env_key = None
for c in candidates:
    if os.path.isabs(c) and c.rstrip(os.sep).endswith(os.sep + 'check'):
        env_key = os.path.basename(os.path.dirname(c.rstrip(os.sep)))
        break

if env_key:
    env_cfg = data.get(env_key, None)
    if isinstance(env_cfg, dict):
        env_checks = (env_cfg.get('$NAME', []) or [])
        if env_checks:
            out[env_key] = ' '.join(env_checks)
print(json.dumps(out))" 2>/dev/null)
    if [ -z "$CHECKS_DICT" ]; then
        CHECKS_DICT="{}"
    fi

    CHECK_KEYS=$(python3 -c "import json, sys
try:
    d = json.loads(sys.argv[1]) or {}
except Exception:
    d = {}
print(' '.join(d.keys()))" "$CHECKS_DICT" 2>/dev/null)

    if [ -n "$ONLY_CHECK" ]; then
        CHECK_KEYS="__only__"
    elif [ -z "$CHECK_KEYS" ]; then
        if [ "$COMPACT_MODE" = true ]; then
            log_line "INFO" "No checks found for ${NAME} (${ENGINE})."
        else
            echo -e "  ${GRAY}• No checks found for $NAME in $ENGINE${RESET}"
        fi
        return
    fi

    run_check_list() {
        local CHECKS="$1"
        for check_name in $CHECKS; do
            check_script=""
            check_path=""

            # Normalize potential JSON-printed quotes around the token
            norm_name="${check_name%\"}"
            norm_name="${norm_name#\"}"
            norm_name="${norm_name%\'}"
            norm_name="${norm_name#\'}"

            if [[ "$norm_name" == @script_path.get* ]]; then
                check_key="${norm_name#@script_path.get(}"
                check_key="${check_key%)}"
                check_key="${check_key//\"/}"
                check_key="${check_key//\'/}"

                SCRIPT_PATH_CANDIDATES=$(ROOT_PATH="$MODULE_ROOT" python3 -c "import json, os, re
p='${CONFIG_JSON}'
root=os.environ.get('ROOT_PATH','')
alts=[]
try:
    with open(p) as f:
        data=json.load(f) or {}
    alts=(data.get('script_path',{}) or {}).get('alternative',[]) or []
except Exception:
    alts=[]

if isinstance(alts, str):
    alts = [alts]
elif not isinstance(alts, list):
    alts = []

out=[]
for a in alts:
    if not isinstance(a,str):
        continue
    a = a.strip()
    if os.path.isabs(a) and a.rstrip(os.sep).endswith(os.sep + 'check'):
        out.append(a)
        continue
    m=re.match(r\"^@root_path\\.joinpath\\(['\\\"](.+?)['\\\"]\\)\\s*$\", a)
    if m:
        rel=m.group(1).replace('.', os.sep)
        out.append(os.path.join(root, rel))

for item in out:
    print(item)")

                for base in $SCRIPT_PATH_CANDIDATES; do
                    if [ -d "$base" ]; then
                        for candidate in \
                            "$base/infra/$check_key/init.sh" \
                            "$base/$check_key/init.sh"
                        do
                            if [ -f "$candidate" ]; then
                                check_script="$candidate"
                                break 2
                            fi
                        done
                    fi
                done
            fi

            if [ -z "$check_script" ]; then
                if [[ "$check_name" == *.* ]]; then
                    check_path="${check_name//./\/}"
                    check_path="${check_path//\\/}"

                    for candidate in \
                        "$MODULE_ROOT/$check_path/init.sh" \
                        "$MODULE_ROOT/check/$check_path/init.sh" \
                        "$ONTOBDC_DIR/$check_path/init.sh" \
                        "$ONTOBDC_DIR/check/$check_path/init.sh"
                    do
                        if [ -f "$candidate" ]; then
                            check_script="$candidate"
                            break
                        fi
                    done
                    if [ -z "$check_script" ]; then
                        check_script="$MODULE_ROOT/$check_path/init.sh"
                    fi
                else
                    check_path="$check_name"
                    check_script="$DIR/$check_path/init.sh"
                fi
            fi
            
            if [ -f "$check_script" ]; then
                DESCRIPTION=""
                unset -f check
                unset -f repair
                unset -f hotfix

                # shellcheck disable=SC1090
                source "$check_script"
                
                if [ -z "$DESCRIPTION" ]; then
                    DESCRIPTION="$check_name"
                fi

                check
                RET_CODE=$?

                if [ $RET_CODE -eq 0 ]; then
                     if [ "$COMPACT_MODE" = true ]; then
                         log_line "SUCCESS" "${DESCRIPTION}"
                     else
                         echo -e "  ${GREEN}✓ ${DESCRIPTION}${RESET}"
                     fi
                else
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
                         if [ "$IS_FATAL" = true ]; then
                             if [ "$COMPACT_MODE" = true ]; then
                                 log_line "ERROR" "${DESCRIPTION} (FATAL)"
                             else
                                 echo -e "  ${RED}✗ ${DESCRIPTION} (FATAL)${RESET}"
                             fi
                             if type repair &>/dev/null; then
                                 repair
                             else
                                 if [ "$COMPACT_MODE" = true ]; then
                                     log_line "ERROR" "Fatal error: ${DESCRIPTION} failed and no repair is available."
                                 else
                                     echo -e "${RED}FATAL ERROR: ${DESCRIPTION} failed and no repair available.${RESET}"
                                 fi
                                 exit 1
                             fi
                         fi

                         if [ "$REPAIR_MODE" = true ]; then
                             if [ "$COMPACT_MODE" = true ]; then
                                 log_line "WARNING" "Attempting repair: ${DESCRIPTION}"
                             else
                                 echo -e "  ${YELLOW}⚡ Attempting repair for: ${DESCRIPTION}...${RESET}"
                             fi
                             if type repair &>/dev/null; then
                                 repair
                                 
                                 check
                                 if [ $? -eq 0 ]; then
                                     if [ "$COMPACT_MODE" = true ]; then
                                         log_line "SUCCESS" "${DESCRIPTION} (Repaired)"
                                     else
                                         echo -e "  ${GREEN}✓ ${DESCRIPTION} (Repaired)${RESET}"
                                     fi
                                     WARNINGS+=("${DESCRIPTION} (Repaired)")
                                 else
                                     if [ "$COMPACT_MODE" = true ]; then
                                         log_line "ERROR" "${DESCRIPTION} (Repair failed)"
                                     else
                                         echo -e "  ${RED}✗ ${DESCRIPTION} (Repair failed)${RESET}"
                                     fi
                                     ERRORS+=("${DESCRIPTION}")
                                 fi
                             else
                                 if [ "$COMPACT_MODE" = true ]; then
                                     log_line "ERROR" "${DESCRIPTION} (No repair function)"
                                 else
                                     echo -e "  ${RED}✗ ${DESCRIPTION} (No repair function)${RESET}"
                                 fi
                                 ERRORS+=("${DESCRIPTION}")
                             fi
                         else
                             if [ "$COMPACT_MODE" = true ]; then
                                 log_line "ERROR" "${DESCRIPTION}"
                             else
                                 echo -e "  ${RED}✗ ${DESCRIPTION}${RESET}"
                             fi
                             ERRORS+=("${DESCRIPTION}")
                             if [ "$ON_FAILURE" = "terminate" ]; then
                                 if [ "$COMPACT_MODE" = true ]; then
                                     log_line "WARNING" "Stopping checks (on_failure=terminate)."
                                 else
                                     echo -e "  ${YELLOW}Stopping checks (on_failure=terminate)${RESET}"
                                 fi
                                 exit 1
                             fi
                         fi
                     fi
                fi
            else
                 if [ "$COMPACT_MODE" = true ]; then
                     log_line "WARNING" "Check script not found: ${check_script}"
                 else
                     echo -e "  ${YELLOW}Warning: Check script not found: $check_script${RESET}"
                 fi
                 ERRORS+=("Check script not found: ${check_script}")
                 if [ "$ON_FAILURE" = "terminate" ]; then
                     if [ "$COMPACT_MODE" = true ]; then
                         log_line "WARNING" "Stopping checks (on_failure=terminate)."
                     else
                         echo -e "  ${YELLOW}Stopping checks (on_failure=terminate)${RESET}"
                     fi
                     exit 1
                 fi
            fi
        done
    }

    if [ -n "$ONLY_CHECK" ]; then
        run_check_list "$ONLY_CHECK"
        return
    fi

    FIRST_SECTION=true
    for SECTION in $CHECK_KEYS; do
        CHECKS_FOR_SECTION=$(python3 -c "import json, sys
try:
    d = json.loads(sys.argv[1]) or {}
except Exception:
    d = {}
print(d.get(sys.argv[2], ''))" "$CHECKS_DICT" "$SECTION" 2>/dev/null)

        if [ -z "$CHECKS_FOR_SECTION" ]; then
            continue
        fi

        if [ "$FIRST_SECTION" = false ]; then
            echo ""
        fi
        FIRST_SECTION=false

        if [ "$SECTION" = "base" ]; then
            if [ "$COMPACT_MODE" = true ]; then
                log_line "INFO" "Checking base checks..."
            else
                echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}base${RESET}"
            fi
        elif [ "$SECTION" = "engine" ]; then
            if [ "$COMPACT_MODE" = true ]; then
                log_line "INFO" "Checking engine checks (${ENGINE})..."
            else
                echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}engine: ${ENGINE}${RESET}"
            fi
        else
            if [ "$COMPACT_MODE" = true ]; then
                log_line "INFO" "Checking ${SECTION} checks..."
            else
                echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}${SECTION}${RESET}"
            fi
        fi

        run_check_list "$CHECKS_FOR_SECTION"
    done

    


}

# Determine Engine
# Try to load from .__ontobdc__/config.yaml
CONFIG_YAML=".__ontobdc__/config.yaml"
ENGINE="venv" # Default fallback

if [ -f "$CONFIG_YAML" ]; then
    DETECTED_ENGINE=$(python3 -c "import re
p='$CONFIG_YAML'
engine=''
try:
    import yaml
    with open(p) as f:
        c = yaml.safe_load(f) or {}
    engine = (c or {}).get('engine', '') or ''
except Exception:
    try:
        with open(p) as f:
            for line in f:
                m = re.match(r'^\\s*engine\\s*:\\s*(\\S+)\\s*$', line)
                if m:
                    engine = m.group(1)
                    break
    except Exception:
        engine = ''
print(engine)")
    if [ ! -z "$DETECTED_ENGINE" ]; then
        ENGINE="$DETECTED_ENGINE"
    fi
elif [ -d "/content" ]; then
    # Heuristic for colab if config doesn't exist
    ENGINE="colab"
fi

if [ ! -f "$CONFIG_JSON" ]; then
    echo -e "  ${RED}✗ Config file not found: ${CONFIG_JSON}${RESET}"
    exit 1
fi

CONFIG_ENGINES=$(python3 -c "import json; 
with open('$CONFIG_JSON') as f: data = json.load(f); 
print(' '.join((data.get('config', {}) or {}).get('engine', [])))" 2>/dev/null)

if [ -n "$CONFIG_ENGINES" ]; then
    ENGINE_ALLOWED=false
    for e in $CONFIG_ENGINES; do
        if [ "$e" = "$ENGINE" ]; then
            ENGINE_ALLOWED=true
            break
        fi
    done
    if [ "$ENGINE_ALLOWED" = false ]; then
        ENGINE="$(echo "$CONFIG_ENGINES" | awk '{print $1}')"
    fi
fi

if [ -n "$ONLY_CHECK" ]; then
    if [[ "$ONLY_CHECK" == *.* ]]; then
        SCOPES="${ONLY_CHECK%%.*}"
    else
        SCOPES="infra"
    fi
elif [[ "$SCOPE" == "all" ]]; then
    SCOPES=$(python3 -c "import json; 
with open('$CONFIG_JSON') as f: data = json.load(f); 
base=(data.get('base', {}) or {})
keys=[]
if isinstance(base, dict):
    for k,v in base.items():
        if isinstance(v, list):
            keys.append(k)
print(' '.join(keys))" 2>/dev/null)
else
    SCOPES="$SCOPE"
fi

for scope_name in $SCOPES; do
    CHECK_DIR="${ONTOBDC_DIR}/check/${scope_name}"
    if [[ ! -d "${CHECK_DIR}" ]]; then
        for candidate in \
            "$MODULE_ROOT/wip/src/infobim/check/${scope_name}" \
            "$MODULE_ROOT/wip/src/infobim/check/infra" \
            "$MODULE_ROOT/core/src/infobim/check/${scope_name}" \
            "$MODULE_ROOT/core/src/infobim/check/infra"
        do
            if [[ -d "${candidate}" ]]; then
                CHECK_DIR="${candidate}"
                break
            fi
        done
        if [[ ! -d "${CHECK_DIR}" ]]; then
            echo -e "  ${YELLOW}Warning: Checks directory not found: ${ONTOBDC_DIR}/check/${scope_name}${RESET}"
        fi
    fi
    run_checks "${CHECK_DIR}" "${scope_name}" "$ENGINE"
done

# if [ -z "$VIRTUAL_ENV" ] && [ -f "venv/bin/activate" ]; then
#     # shellcheck disable=SC1091
#     source "venv/bin/activate"
# fi

echo ""

if [ ${#ERRORS[@]} -eq 0 ]; then
    MSG="All checks passed."
    if [ "$IGNORE_WARNINGS" != true ] && [ ${#WARNINGS[@]} -gt 0 ]; then
        MSG="${MSG}\n\nWarnings:"
        for w in "${WARNINGS[@]}"; do
            MSG="${MSG}\n• $w"
        done
    fi
    if [ "$COMPACT_MODE" = true ]; then
        log_line "SUCCESS" "System checks passed."
        if [ "$IGNORE_WARNINGS" != true ] && [ ${#WARNINGS[@]} -gt 0 ]; then
            log_line "WARNING" "Warnings: ${#WARNINGS[@]}"
            for w in "${WARNINGS[@]}"; do
                log_line "WARNING" "$w"
            done
        fi
    else
        if type print_message_box &>/dev/null; then
            print_message_box "GREEN" "Success" "System Operational" "$MSG"
        else
            echo -e "${GREEN}Success: System Operational${RESET}\n$MSG"
        fi
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
    
    if [ "$COMPACT_MODE" = true ]; then
        log_line "ERROR" "System checks failed (${#ERRORS[@]})."
        if [ "$IGNORE_WARNINGS" != true ] && [ ${#WARNINGS[@]} -gt 0 ]; then
            log_line "WARNING" "Warnings: ${#WARNINGS[@]}"
            for w in "${WARNINGS[@]}"; do
                log_line "WARNING" "$w"
            done
        fi
    else
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "System Check Failed" "$MSG"
        else
            echo -e "${RED}Error: System Check Failed${RESET}\n$MSG"
        fi
    fi
    exit 1
fi
