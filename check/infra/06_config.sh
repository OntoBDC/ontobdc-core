DESCRIPTION="Infra: OntoBDC config file"

CONFIG_DIR="./config"
CONFIG_FILE="./config/ontobdc.yaml"

check() {
    if [[ ! -d "$CONFIG_DIR" ]]; then
        return 1
    fi
    if [[ ! -f "$CONFIG_FILE" ]]; then
        return 1
    fi
    grep -qE '^[[:space:]]*modules:' "$CONFIG_FILE" || return 1
    grep -qE '^[[:space:]]*-[[:space:]]*install:' "$CONFIG_FILE" || return 1
    grep -qE '^[[:space:]]*engine:' "$CONFIG_FILE" || return 1
    grep -qE '^[[:space:]]*-[[:space:]]*dev:' "$CONFIG_FILE" || return 1
    grep -qE '^[[:space:]]*source:[[:space:]]*ontobdc/dev' "$CONFIG_FILE" || return 1
    grep -qE '^[[:space:]]*-[[:space:]]*run:' "$CONFIG_FILE" || return 1
    grep -qE '^[[:space:]]*source:[[:space:]]*ontobdc/run' "$CONFIG_FILE" || return 1
    return 0
}

repair() {
    if [[ ! -d "$CONFIG_DIR" ]]; then
        mkdir -p "$CONFIG_DIR"
    fi

    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local TEMPLATE_FILE="${SCRIPT_DIR}/06_config/ontobdc.yaml"

    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        return 1
    fi

    # If config does not exist yet, create it from template
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cat "$TEMPLATE_FILE" > "$CONFIG_FILE"
        return 0
    fi

    # If any required structure is missing, append template content
    if ! check; then
        cat "$TEMPLATE_FILE" >> "$CONFIG_FILE"
    fi
}
