#!/bin/bash

MODULE_ROOT="$(
    PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd):${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_root_dir; print(get_root_dir())" 2>/dev/null
)"

SCRIPT_DIR="$(
    PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd):${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_script_dir; print(get_script_dir())" 2>/dev/null
)"

MESSAGE_BOX="${SCRIPT_DIR}/cli/message_box.sh"

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
    print_message_box() {
        echo "[$1] $2: $3"
        echo -e "$4"
    }
fi

WIREFORM_SH="${SCRIPT_DIR}/cli/adapter/wireform.sh"
if [ -f "${WIREFORM_SH}" ]; then
    source "${WIREFORM_SH}"
fi

echo ""
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo -e "${CYAN}Creating the Execution Plan...${RESET}"
echo -e "${GRAY}${FULL_HLINE}${RESET}"
echo ""

# Add src to PYTHONPATH
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"

# Execute dag.py
python3 "${SCRIPT_DIR}/plan/dag.py" "$@"






