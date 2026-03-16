DESCRIPTION="Infra: Root Absolute Path Configured"

resolve_config_path() {
    local candidates=(
        ".__ontobdc__/config.yaml"
        "../.__ontobdc__/config.yaml"
        "../../.__ontobdc__/config.yaml"
    )
    for p in "${candidates[@]}"; do
        if [ -f "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    return 1
}

check() {
    local CONFIG_PATH
    CONFIG_PATH=$(resolve_config_path) || true

    if [ -z "$CONFIG_PATH" ]; then
        if type print_message_box &>/dev/null; then
            bash "/Users/eliasmpjunior/infobim/deploy/ontobdc-stack/core/src/ontobdc/cli/print_log.sh" "ERROR" "Root Directory Not Configured" "reason=missing .__ontobdc__/config.yaml" "hint=run 'ontobdc check --repair' from project root"
        else
            echo "Error: Missing .__ontobdc__/config.yaml. Run 'ontobdc check --repair' from the project root."
        fi
        return 1
    fi

    local IS_OK
    IS_OK=$(python3 -c "import os, sys
try:
    import yaml
except Exception:
    print('false')
    sys.exit(0)
path='$CONFIG_PATH'
try:
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    ap = (((cfg.get('directory') or {}).get('root') or {}).get('absolute_path') or '')
    if isinstance(ap, str) and ap.strip() and os.path.isdir(ap.strip()):
        print('true')
    else:
        print('false')
except Exception:
    print('false')
")

    if [ "$IS_OK" = "true" ]; then
        return 0
    fi

    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Root Directory Not Configured" "The directory.root.absolute_path is missing or invalid in:\n\n  $CONFIG_PATH\n\nRun this from the project root:\n\n  ontobdc check --repair"
    else
        echo "Error: directory.root.absolute_path is missing/invalid in $CONFIG_PATH. Run 'ontobdc check --repair' from the project root."
    fi
    return 1
}

hotfix() {
    return 1
}

repair() {
    mkdir -p .__ontobdc__ >/dev/null 2>&1

    python3 -c "import os, sys
try:
    import yaml
except Exception as e:
    sys.exit(1)
path='.__ontobdc__/config.yaml'
cfg={}
if os.path.exists(path):
    try:
        with open(path, 'r') as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg={}
cfg.setdefault('directory', {}).setdefault('root', {})['absolute_path'] = os.getcwd()
with open(path, 'w') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
"

    if [ $? -eq 0 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "GREEN" "Success" "Root Directory Configured" "Saved directory.root.absolute_path to:\n\n  .__ontobdc__/config.yaml"
        else
            echo "Success: Saved directory.root.absolute_path to .__ontobdc__/config.yaml"
        fi
        return 0
    fi

    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Repair Failed" "Could not write .__ontobdc__/config.yaml.\n\nRun this from the project root:\n\n  ontobdc check --repair"
    else
        echo "Error: Repair failed. Run 'ontobdc check --repair' from the project root."
    fi
    return 1
}
