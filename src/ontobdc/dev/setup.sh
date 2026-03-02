#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

ENGINE="$1"
if [[ -z "$ENGINE" ]]; then
    ENGINE="venv"
fi

if [[ "$ENGINE" != "venv" && "$ENGINE" != "colab" ]]; then
    echo "Invalid engine '$ENGINE'. Allowed values: venv, colab."
    exit 1
fi

MAIN_CONFIG="${ROOT_DIR}/config/ontobdc.yaml"

mkdir -p "$(dirname "$MAIN_CONFIG")"

{
    echo "modules:"
    echo "  - install:"
    echo "      engine: ${ENGINE}"
    echo "  - dev:"
    echo "      source: ontobdc/dev"
    echo "  - run:"
    echo "      source: ontobdc/run"
} > "$MAIN_CONFIG"

echo "ontobdc configuration written to config/ontobdc.yaml with engine='${ENGINE}'"
