#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "$ROOT_DIR" || exit 1

ENGINE="venv"
CONFIG_FILE="config/ontobdc.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    ENGINE=$(awk '
        /^[[:space:]]*-[[:space:]]*install:/ { in_inst=1; next }
        /^[[:space:]]*-[[:space:]]*[^[:space:]]/ && in_inst { exit }
        in_inst && $1 ~ /engine:/ {
            for (i=2; i<=NF; i++) {
                printf "%s%s", $i, (i<NF?" ":"")
            }
            print ""
            exit
        }
    ' "$CONFIG_FILE")
    [[ -z "$ENGINE" ]] && ENGINE="venv"
fi

if [ "$ENGINE" != "colab" ]; then
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    elif [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    else
        echo "Virtual environment not found in venv/ or .venv/"
        echo "Please run './ontobdc/cli/check.sh --repair' to setup the environment."
        exit 1
    fi
fi

exec python3 stack/run/run.py "$@"
