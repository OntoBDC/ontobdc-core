
show_help() {
    RAW_BOLD="\\033[1m"
    RAW_RESET="\\033[0m"
    RAW_CYAN="\\033[36m"
    RAW_GRAY="\\033[90m"
    RAW_WHITE="\\033[37m"

    HELP_CONTENT=$(
        cat <<EOF
${RAW_WHITE}Usage:${RAW_RESET}
  ${RAW_GRAY}ontobdc storage [${RAW_CYAN}--json${RAW_GRAY}]${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--create${RAW_GRAY} <path>${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--container-id${RAW_GRAY} <container_id> ${RAW_CYAN}--create${RAW_GRAY} <dataset_id>${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--local${RAW_GRAY} [path]${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--remove${RAW_GRAY} <dataset_id>${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--refresh${RAW_GRAY} [dataset_id]${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--resource${RAW_GRAY} <file_path>${RAW_RESET}
    ${RAW_GRAY}(${RAW_CYAN}--schema${RAW_GRAY} <schema_path> | ${RAW_CYAN}--ontology${RAW_GRAY} <ontology_path>)${RAW_RESET}
  ${RAW_GRAY}ontobdc storage ${RAW_CYAN}--help${RAW_RESET}

${RAW_WHITE}Options:${RAW_RESET}
  ${RAW_CYAN}--create${RAW_RESET} <path>                 ${RAW_GRAY}Create a new local storage container at the given path${RAW_RESET}
  ${RAW_CYAN}--container-id${RAW_RESET} <container_id>   ${RAW_GRAY}Target a registered container and create a dataset with ${RAW_CYAN}--create${RAW_RESET}${RAW_GRAY}${RAW_RESET}
  ${RAW_CYAN}--local${RAW_RESET} [path]                 ${RAW_GRAY}Register a local storage path (default: current directory)${RAW_RESET}
  ${RAW_CYAN}--remove${RAW_RESET} <dataset_id>          ${RAW_GRAY}Remove a dataset from the storage index${RAW_RESET}
  ${RAW_CYAN}--refresh${RAW_RESET} [dataset_id]         ${RAW_GRAY}Rebuild storage metadata (all datasets or a single dataset)${RAW_RESET}
  ${RAW_CYAN}--resource${RAW_RESET} <file_path>         ${RAW_GRAY}Create resource data only${RAW_RESET}
    ${RAW_CYAN}--schema${RAW_RESET} <schema_path>       ${RAW_GRAY}Schema file path${RAW_RESET}
    ${RAW_CYAN}--ontology${RAW_RESET} <ontology_path>   ${RAW_GRAY}Ontology file path (JSON-LD, TTL, RDF)${RAW_RESET}
  ${RAW_CYAN}--json${RAW_RESET}                         ${RAW_GRAY}Output the storage list as JSON (no table rendering)${RAW_RESET}
  ${RAW_CYAN}-h${RAW_RESET}, ${RAW_CYAN}--help${RAW_RESET}                     ${RAW_GRAY}Show this help${RAW_RESET}
EOF
    )

    if type print_message_box &>/dev/null; then
        print_message_box "GRAY" "OntoBDC" "Storage" "${HELP_CONTENT}"
    else
        echo -e "$HELP_CONTENT"
    fi
}

WHITE="\033[37m"
RESET="\033[0m"

MESSAGE_BOX_SCRIPT="$(python3 -c "from ontobdc.cli import get_message_box_script; print(get_message_box_script())" 2>/dev/null)"
if [ -n "$MESSAGE_BOX_SCRIPT" ] && [ -f "$MESSAGE_BOX_SCRIPT" ]; then
    source "$MESSAGE_BOX_SCRIPT"
fi

# Check if storage is enabled
STORAGE_ENABLED=$(PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd):${PYTHONPATH:-}" python3 -c "import sys; from ontobdc.storage import is_enabled; sys.stdout.write('1' if is_enabled() else '0')" 2>/dev/null)

if [ "$STORAGE_ENABLED" != "1" ]; then
    MSG=" The storage module is not enabled in your current environment.\n\n To enable it, run:\n   ontobdc storage --enable"
    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Storage Disabled" "$MSG"
    else
        echo -e "Error: $MSG"
    fi
    exit 1
fi

if type print_message_box &>/dev/null; then
    print_message_box "RED" "Error" "Invalid command" " The command ${WHITE}ontobdc storage $1${RESET} is invalid."
else
    echo -e "Error: The command 'ontobdc storage $1' is invalid."
fi

exit 1
