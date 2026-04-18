#!/bin/bash

clear

SCRIPT_DIR="$(
    PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd):${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_script_dir; print(get_script_dir())" 2>/dev/null
)"

MESSAGE_BOX_SCRIPT="$(python3 -c "from ontobdc.cli import get_message_box_script; print(get_message_box_script())" 2>/dev/null)"
if [ -n "$MESSAGE_BOX_SCRIPT" ] && [ -f "$MESSAGE_BOX_SCRIPT" ]; then
    source "$MESSAGE_BOX_SCRIPT"
fi

show_help() {
    if type print_message_box &>/dev/null; then
        print_message_box "GRAY" "OntoBDC" "Storage" "Usage:\n  ontobdc storage [--json]\n  ontobdc storage --local [path]\n  ontobdc storage --remove <dataset_id>\n  ontobdc storage --refresh [dataset_id]\n  ontobdc storage --resource <file_path> (--schema <schema_path> | --entity <entity_id>) --check\n\nOptions:\n  --json                                                     Output list in JSON format\n  --local [path]                                             Initialize local storage (default: current directory)\n  --remove <dataset_id>                                      Remove a dataset from storage index\n  --refresh [dataset_id]                                     Rebuild storage metadata when changes are detected\n  --resource <file_path> (--schema <schema> | --entity <id>) --check  Validate resource data only\n  -h                                                         Show this help"
    else
        echo "Usage:"
        echo "  ontobdc storage [--json]"
        echo "  ontobdc storage --local [path]"
        echo "  ontobdc storage --remove <dataset_id>"
        echo "  ontobdc storage --refresh [dataset_id]"
        echo "  ontobdc storage --resource <file_path> (--schema <schema_path> | --entity <entity_id>)"
        echo "  ontobdc storage --resource <file_path> (--schema <schema_path> | --entity <entity_id>) --check"
        echo ""
        echo "Options:"
        echo "  --json                  Output list in JSON format"
        echo "  --local [path]          Initialize local storage (default: current directory)"
        echo "  --remove <dataset_id>   Remove a dataset from storage index"
        echo "  --refresh [dataset_id]  Rebuild storage metadata when changes are detected"
        echo "  --resource <file_path> (--schema <schema_path> | --entity <entity_id>) --check  Validate resource data only"
        echo "  -h                Show this help"
    fi
}

if [ "$#" -eq 0 ] || [ "$1" = "--json" ]; then
    OUTPUT=$(python3 "${SCRIPT_DIR}/storage/list.py" "$@" 2>/dev/null)

    if [ -z "$OUTPUT" ] || [ "$OUTPUT" = "[]" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "YELLOW" "Warning" "OntoBDC Storage" "No storage has been initialized yet.\n\nInitialize it with:\n  ontobdc storage --local [path]"
        else
            echo "No storage has been initialized yet."
            echo ""
            echo "Initialize it with:"
            echo "  ontobdc storage --local [path]"
        fi
        exit 0
    fi
    
    if [ "$1" = "--json" ]; then
        # Usa python json.tool nativo para mostrar o JSON identado
        echo "$OUTPUT" | python3 -m json.tool
    else
        # Passa o JSON capturado para o script Python renderizar usando o Rich
        echo "$OUTPUT" | python3 "${SCRIPT_DIR}/storage/render_list.py"
    fi
    exit 0
fi

if [ "$#" -gt 0 ]; then
    if [ "$1" = "help" ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_help
        exit 0
    fi
fi

if [ "$1" = "--local" ]; then
    python3 "${SCRIPT_DIR}/storage/local.py" "$@"
    exit $?
fi

if [ "$1" = "--remove" ]; then
    python3 "${SCRIPT_DIR}/storage/remove.py" "$@"
    exit $?
fi

if [ "$1" = "--refresh" ]; then
    python3 "${SCRIPT_DIR}/storage/refresh.py" "$@"
    exit $?
fi

if [ "$1" = "--resource" ]; then
    for arg in "$@"; do
        if [ "$arg" = "--check" ]; then
            python3 "${SCRIPT_DIR}/storage/check.py" "$@"
            exit $?
        fi
    done
    python3 "${SCRIPT_DIR}/storage/resource.py" "$@"
    exit $?
fi

show_help
exit 1
