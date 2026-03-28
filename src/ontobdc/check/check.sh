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

    if [ ! -f "$CONFIG_JSON" ]; then
         echo -e "  ${RED}✗ Config file not found: ${CONFIG_JSON}${RESET}"
         ERRORS+=("Config file missing")
         return
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

    if [ -z "$CHECK_KEYS" ]; then
        echo -e "  ${GRAY}• No checks found for $NAME in $ENGINE${RESET}"
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
                     echo -e "  ${GREEN}✓ ${DESCRIPTION}${RESET}"
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
                             echo -e "  ${RED}✗ ${DESCRIPTION} (FATAL)${RESET}"
                             if type repair &>/dev/null; then
                                 repair
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
                 echo -e "  ${YELLOW}Warning: Check script not found: $check_script${RESET}"
            fi
        done
    }

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
            echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}base${RESET}"
        elif [ "$SECTION" = "engine" ]; then
            echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}engine: ${ENGINE}${RESET}"
        else
            echo -e "${YELLOW}❯ ${WHITE}Checking ${CYAN}${SECTION}${RESET}"
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

if [[ "$SCOPE" == "all" ]]; then
    SCOPES=$(python3 -c "import json; 
with open('$CONFIG_JSON') as f: data = json.load(f); 
print(' '.join((data.get('base', {}) or {}).keys()))" 2>/dev/null)
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
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        MSG="${MSG}\n\nWarnings:"
        for w in "${WARNINGS[@]}"; do
            MSG="${MSG}\n• $w"
        done
    fi
    if type print_message_box &>/dev/null; then
        print_message_box "GREEN" "Success" "System Operational" "$MSG"
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
        print_message_box "RED" "Error" "System Check Failed" "$MSG"
    else
        echo -e "${RED}Error: System Check Failed${RESET}\n$MSG"
    fi
    exit 1
fi
