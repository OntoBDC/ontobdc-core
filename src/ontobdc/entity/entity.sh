#!/bin/bash

clear

PY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SCRIPT_DIR="$(
    PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_script_dir; print(get_script_dir())" 2>/dev/null
)"

MESSAGE_BOX_SCRIPT="$(PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "from ontobdc.cli import get_message_box_script; print(get_message_box_script())" 2>/dev/null)"
if [ -n "$MESSAGE_BOX_SCRIPT" ] && [ -f "$MESSAGE_BOX_SCRIPT" ]; then
    source "$MESSAGE_BOX_SCRIPT"
fi

PROJECT_ROOT=""
if [ -n "${ONTOBDC_PROJECT_ROOT:-}" ]; then
    PROJECT_ROOT="$ONTOBDC_PROJECT_ROOT"
else
    PROJECT_ROOT="$(PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "from ontobdc.cli import get_root_dir; print(get_root_dir() or '')" 2>/dev/null)"
fi

if [ -z "${PROJECT_ROOT:-}" ]; then
    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Project Root Not Found" "Could not find .__ontobdc__/config.yaml.\n\nRun this from the project root."
    else
        echo "Error: Could not find .__ontobdc__/config.yaml. Run this from the project root."
    fi
    exit 1
fi

show_help() {
    if type print_message_box &>/dev/null; then
        print_message_box "GRAY" "OntoBDC" "Entity Framework" "Usage:\n  ontobdc entity\n  ontobdc entity --list\n  ontobdc entity --enable <true|false>\n  ontobdc entity --purge\n  ontobdc entity --create <unique_name>\n\nOptions:\n  --list                  List available entities\n  --enable <true|false>   Enable/disable Entity Framework in .__ontobdc__/config.yaml\n  --create <unique_name>  Create a new entity with the given unique name\n  --purge                 Remove Entity Framework state and delete .__ontobdc__/payload and .__ontobdc__/ontology\n  -h                      Show this help"
    else
        echo "Usage:"
        echo "  ontobdc entity"
        echo "  ontobdc entity --list"
        echo "  ontobdc entity --enable <true|false>"
        echo "  ontobdc entity --purge"
        echo "  ontobdc entity --create <unique_name>"
        echo ""
        echo "Options:"
        echo "  --list                  List available entities"
        echo "  --enable <true|false>   Enable/disable Entity Framework in .__ontobdc__/config.yaml"
        echo "  --purge                 Remove Entity Framework state and delete .__ontobdc__/payload and .__ontobdc__/ontology"
        echo "  --create <unique_name>  Create a new entity with the given unique name"
        echo "  -h                      Show this help"
    fi
}

if [ "$#" -gt 0 ]; then
    if [ "$1" = "help" ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_help
        exit 0
    fi
fi

if [ "$#" -gt 0 ] && [ "$1" = "--purge" ]; then
    if [ "$#" -ne 1 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Invalid Arguments" "Usage:\n  ontobdc entity --purge"
        else
            echo "Error: Usage: ontobdc entity --purge"
        fi
        exit 1
    fi

    CURRENT_ENTITY_FRAMEWORK_ENABLED="$(PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "import sys
try:
    import yaml
except Exception:
    print('false'); sys.exit(0)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
try:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    val = ((cfg.get('entity') or {}).get('framework') or '')
    print('true' if str(val).strip() == 'enable' else 'false')
except Exception:
    print('false')
")"

    if [ "$CURRENT_ENTITY_FRAMEWORK_ENABLED" = "true" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Purge Blocked" "Entity Framework is enabled.\n\nDisable it before purging:\n  ontobdc entity --enable false"
        else
            echo "Error: Entity Framework is enabled."
            echo ""
            echo "Disable it before purging:"
            echo "  ontobdc entity --enable false"
        fi
        exit 1
    fi

    rm -rf "${PROJECT_ROOT}/.__ontobdc__/payload" >/dev/null 2>&1 || true
    rm -rf "${PROJECT_ROOT}/.__ontobdc__/ontology" >/dev/null 2>&1 || true
    rm "${PROJECT_ROOT}/.__ontobdc__/entity.rdf" >/dev/null 2>&1 || true

    PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "import os, sys
try:
    import yaml
except Exception:
    sys.exit(1)
project_root='${PROJECT_ROOT}'
path=os.path.join(project_root, '.__ontobdc__', 'config.yaml')
if not os.path.exists(path):
    sys.exit(0)
with open(path, 'r') as f:
    cfg = yaml.safe_load(f) or {}
if isinstance(cfg, dict) and 'entity' in cfg:
    del cfg['entity']
with open(path, 'w') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
"
    if [ $? -ne 0 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Purge Failed" "Failed to update .__ontobdc__/config.yaml"
        else
            echo "Error: Failed to update .__ontobdc__/config.yaml"
        fi
        exit 1
    fi

    if type print_message_box &>/dev/null; then
        print_message_box "GREEN" "Success" "Entity Framework Purged" "Removed entity.framework from .__ontobdc__/config.yaml and deleted:\n\n  .__ontobdc__/payload/\n  .__ontobdc__/ontology/"
    else
        echo "Success: Entity Framework purged."
    fi
    exit 0
fi

if [ "$#" -gt 0 ] && [ "$1" = "--enable" ]; then
    if [ "$#" -ne 2 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Invalid Arguments" "Usage:\n  ontobdc entity --enable <true|false>"
        else
            echo "Error: Usage: ontobdc entity --enable <true|false>"
        fi
        exit 1
    fi

    if [ "$2" != "true" ] && [ "$2" != "false" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Invalid Value" "Expected true or false.\n\nUsage:\n  ontobdc entity --enable <true|false>"
        else
            echo "Error: Expected true or false. Usage: ontobdc entity --enable <true|false>"
        fi
        exit 1
    fi

    CURRENT_ENTITY_FRAMEWORK_ENABLED="$(PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "import sys
try:
    import yaml
except Exception:
    print('false'); sys.exit(0)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
try:
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    val = ((cfg.get('entity') or {}).get('framework') or '')
    print('true' if str(val).strip() == 'enable' else 'false')
except Exception:
    print('false')
")"

    if [ "$2" = "true" ] && [ "$CURRENT_ENTITY_FRAMEWORK_ENABLED" = "true" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "YELLOW" "Warning" "Entity Framework" "Entity Framework is already enabled."
        else
            echo "Warning: Entity Framework is already enabled."
        fi
        exit 0
    fi

    if [ "$2" = "false" ] && [ "$CURRENT_ENTITY_FRAMEWORK_ENABLED" != "true" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "YELLOW" "Warning" "Entity Framework" "Entity Framework is already disabled."
        else
            echo "Warning: Entity Framework is already disabled."
        fi
        exit 0
    fi

    PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "import os, sys
try:
    import yaml
except Exception:
    sys.exit(1)
project_root='${PROJECT_ROOT}'
path=os.path.join(project_root, '.__ontobdc__', 'config.yaml')
cfg={}
if os.path.exists(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg={}
if not isinstance(cfg, dict):
    cfg={}
cfg.setdefault('entity', {})['framework'] = 'enable' if '${2}' == 'true' else 'disable'
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w', encoding='utf-8') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
"
    if [ $? -ne 0 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Write Failed" "Failed to update entity.framework in .__ontobdc__/config.yaml"
        else
            echo "Error: Failed to update entity.framework in .__ontobdc__/config.yaml"
        fi
        exit 1
    fi

    if [ "$2" = "true" ]; then
        if command -v ontobdc >/dev/null 2>&1; then
            ontobdc check --only infra.is_entity_ready -c --ignore-warnings
            if [ $? -ne 0 ]; then
                exit 1
            fi
        else
            PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 "${PY_ROOT}/ontobdc/cli/__init__.py" check --only infra.is_entity_ready -c --ignore-warnings
            if [ $? -ne 0 ]; then
                exit 1
            fi
        fi

        if type print_message_box &>/dev/null; then
            print_message_box "GREEN" "Success" "Entity Framework Enabled" "entity.framework enabled in .__ontobdc__/config.yaml"
        else
            echo "Success: entity.framework enabled in .__ontobdc__/config.yaml"
        fi
    else
        if type print_message_box &>/dev/null; then
            print_message_box "GREEN" "Success" "Entity Framework Disabled" "entity.framework disabled in .__ontobdc__/config.yaml"
        else
            echo "Success: entity.framework disabled in .__ontobdc__/config.yaml"
        fi
    fi
    exit 0
fi

ENTITY_FRAMEWORK_ENABLED="$(PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "import sys
try:
    import yaml
except Exception:
    print('false'); sys.exit(0)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
try:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    val = ((cfg.get('entity') or {}).get('framework') or '')
    print('true' if str(val).strip() == 'enable' else 'false')
except Exception:
    print('false')
")"

if [ "$ENTITY_FRAMEWORK_ENABLED" != "true" ]; then
    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Entity Framework Disabled" "entity.framework is not enabled in .__ontobdc__/config.yaml\n\nRun this once to fix:\n  ontobdc entity --enable true"
    else
        echo "Error: entity.framework is not enabled in .__ontobdc__/config.yaml"
        echo ""
        echo "Run this once to fix:"
        echo "  ontobdc entity --enable true"
    fi
    exit 1
fi

if [ "$#" -eq 0 ]; then
    OUTPUT=$(python3 "$(dirname "${BASH_SOURCE[0]}")/list.py" "--list" 2>/dev/null)
    if [ -z "$OUTPUT" ] || [ "$OUTPUT" = "[]" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "YELLOW" "Warning" "OntoBDC Entity Framework" "No entity has been initialized yet."
        else
            echo "No entity has been initialized yet."
        fi
        exit 0
    fi
    echo "$OUTPUT"
    exit 0
fi

if [ "$1" = "--list" ]; then
    OUTPUT=$(python3 "$(dirname "${BASH_SOURCE[0]}")/list.py" "$@" 2>/dev/null)
    if [ -z "$OUTPUT" ] || [ "$OUTPUT" = "[]" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "YELLOW" "Warning" "OntoBDC Entity Framework" "No entity has been initialized yet."
        else
            echo "No entity has been initialized yet."
        fi
        exit 0
    fi
    echo "$OUTPUT"
    exit 0
fi

if [ "$1" = "--create" ]; then
    if [ "$#" -ne 2 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Invalid Arguments" "Usage:\n  ontobdc entity --create <unique_name>"
        else
            echo "Error: Usage: ontobdc entity --create <unique_name>"
        fi
        exit 1
    fi

    PYTHONPATH="${PY_ROOT}:${PYTHONPATH:-}" python3 -c "import sys
try:
    from ontobdc.entity import create_entity
    create_entity(sys.argv[1])
except Exception as e:
    print(str(e))
    sys.exit(1)
" "$2"
    if [ $? -ne 0 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Entity Create Failed" "Failed to create entity:\n  $2"
        fi
        exit 1
    fi
    echo ""
    exit 0
fi

show_help
exit 1
