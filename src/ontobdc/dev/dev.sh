#!/bin/bash

clear
# Do not clear screen, let the user see previous output
# clear

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MESSAGE_BOX_SCRIPT="${SCRIPT_DIR}/../cli/message_box.sh"
if [ -f "$MESSAGE_BOX_SCRIPT" ]; then
    source "$MESSAGE_BOX_SCRIPT"
fi

if [ "$#" -gt 0 ]; then
    if [ "$1" = "help" ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        source "${SCRIPT_DIR}/help.sh"
        ontobdc_help_dev
        exit 0
    fi
fi

if [ -n "${ONTOBDC_PROJECT_ROOT:-}" ]; then
    PROJECT_ROOT="$ONTOBDC_PROJECT_ROOT"
else
    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Project Root Not Set" "ONTOBDC_PROJECT_ROOT environment variable is not set."
    else
        echo "Error: ONTOBDC_PROJECT_ROOT environment variable is not set."
    fi
    exit 1
fi

(
    cd "$PROJECT_ROOT" || exit 1
    if command -v ontobdc >/dev/null 2>&1; then
        ontobdc check -c
    else
        bash "${PROJECT_ROOT}/wip/src/ontobdc/check/check.sh"
    fi
)
CHECK_EXIT_CODE=$?
if [ $CHECK_EXIT_CODE -ne 0 ]; then
    exit $CHECK_EXIT_CODE
fi

ROOT_DIR=$(python3 -c "import sys
try:
    import yaml
except Exception:
    print('')
    sys.exit(0)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
try:
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    print((((cfg.get('directory') or {}).get('root') or {}).get('absolute_path')) or '')
except Exception:
    print('')
")

clear

ENABLE_DEV_TOOL=false
for arg in "$@"; do
    if [[ "$arg" == "--enable-dev-tool" ]]; then
        ENABLE_DEV_TOOL=true
        break
    fi
done

if [ "$ENABLE_DEV_TOOL" = true ]; then
    if [ "$#" -ne 1 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Invalid Arguments" "--enable-dev-tool must be passed alone."
        else
            echo "Error: --enable-dev-tool must be passed alone."
        fi
        exit 1
    fi

    python3 -c "import os, sys
try:
    import yaml
except Exception:
    sys.exit(1)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
cfg={}
if os.path.exists(path):
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
cfg.setdefault('dev', {})['tool'] = 'enabled'
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
"
    if [ $? -ne 0 ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Write Failed" "Failed to write dev.tool=enabled to .__ontobdc__/config.yaml"
        else
            echo "Error: Failed to write dev.tool=enabled to .__ontobdc__/config.yaml"
        fi
        exit 1
    fi

        if type print_message_box &>/dev/null; then
            print_message_box "GREEN" "Success" "Dev Tool Enabled" "dev.tool enabled in .__ontobdc__/config.yaml"
        else
            echo "Success: dev.tool enabled in .__ontobdc__/config.yaml"
        fi
    exit 0
fi

DEV_TOOL_ENABLED=$(python3 -c "import sys
try:
    import yaml
except Exception:
    print('false')
    sys.exit(0)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
try:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    val = ((cfg.get('dev') or {}).get('tool') or '')
    print('true' if str(val).strip() == 'enabled' else 'false')
except Exception:
    print('false')
")

if [ "$DEV_TOOL_ENABLED" != "true" ]; then
    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Dev Tool Disabled" "dev.tool is not enabled in .__ontobdc__/config.yaml\n\nRun this once to fix:\n  ontobdc dev --enable-dev-tool"
    else
        echo "Error: dev.tool is not enabled in .__ontobdc__/config.yaml"
        echo ""
        echo "Run this once to fix:"
        echo "  ontobdc dev --enable-dev-tool"
    fi
    exit 1
fi

if [ "$#" -gt 0 ]; then
    if [ "$1" = "commit" ]; then
        shift
        if [ "$#" -lt 1 ]; then
            if type print_message_box &>/dev/null; then
                print_message_box "RED" "Error" "Missing Commit Message" "Usage:\n  ontobdc dev commit \"<message>\""
            else
                echo "Error: Missing commit message"
                echo "Usage: ontobdc dev commit \"<message>\""
            fi
            exit 1
        fi

        bash "${SCRIPT_DIR}/commit.sh" "$@"
        exit $?
    fi

    if [ "$1" = "branch-create" ]; then
        shift
        bash "${SCRIPT_DIR}/branch.sh" --create "$@"
        exit $?
    fi

    if [ "$1" = "checkout" ]; then
        shift
        bash "${SCRIPT_DIR}/branch.sh" --checkout "$@"
        exit $?
    fi

    if [ "$1" = "changelog" ]; then
        shift
        bash "${SCRIPT_DIR}/branch.sh" --changelog "$@"
        exit $?
    fi

    if [ "$1" = "branch" ]; then
        shift
        bash "${SCRIPT_DIR}/branch.sh" "$@"
        exit $?
    fi

    if [ "$1" = "repo" ]; then
        shift
        if [ "$#" -lt 1 ]; then
            if type print_message_box &>/dev/null; then
                print_message_box "RED" "Error" "Missing Arguments" "Usage:\n  ontobdc dev repo --add-ssh-key <path>\n  ontobdc dev repo --rm-ssh-key"
            else
                echo "Error: Missing arguments"
                echo "Usage: ontobdc dev repo --add-ssh-key <path>"
                echo "       ontobdc dev repo --rm-ssh-key"
            fi
            exit 1
        fi

        if [ "$1" = "--add-ssh-key" ]; then
            if [ "$#" -ne 2 ]; then
                if type print_message_box &>/dev/null; then
                    print_message_box "RED" "Error" "Invalid Arguments" "Usage:\n  ontobdc dev repo --add-ssh-key <path>"
                else
                    echo "Error: Invalid arguments"
                    echo "Usage: ontobdc dev repo --add-ssh-key <path>"
                fi
                exit 1
            fi

            SSH_KEY_PATH="$2"
            python3 -c "import os, sys
try:
    import yaml
except Exception:
    sys.exit(1)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
cfg={}
if os.path.exists(path):
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
cfg.setdefault('dev', {}).setdefault('repo', {}).setdefault('ssh', {})['key_path'] = '${SSH_KEY_PATH}'
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
"
            if [ $? -ne 0 ]; then
                if type print_message_box &>/dev/null; then
                    print_message_box "RED" "Error" "Write Failed" "Failed to write dev.repo.ssh.key_path to .__ontobdc__/config.yaml"
                else
                    echo "Error: Failed to write dev.repo.ssh.key_path to .__ontobdc__/config.yaml"
                fi
                exit 1
            fi

            if type print_message_box &>/dev/null; then
                print_message_box "GREEN" "Success" "SSH Key Saved" "Saved dev.repo.ssh.key_path in .__ontobdc__/config.yaml"
            else
                echo "Success: Saved dev.repo.ssh.key_path in .__ontobdc__/config.yaml"
            fi
            exit 0
        fi

        if [ "$1" = "--rm-ssh-key" ]; then
            if [ "$#" -ne 1 ]; then
                if type print_message_box &>/dev/null; then
                    print_message_box "RED" "Error" "Invalid Arguments" "Usage:\n  ontobdc dev repo --rm-ssh-key"
                else
                    echo "Error: Invalid arguments"
                    echo "Usage: ontobdc dev repo --rm-ssh-key"
                fi
                exit 1
            fi

            python3 -c "import os, sys
try:
    import yaml
except Exception:
    sys.exit(1)
path='${PROJECT_ROOT}/.__ontobdc__/config.yaml'
cfg={}
if os.path.exists(path):
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
dev = cfg.get('dev') or {}
repo = dev.get('repo') or {}
ssh = repo.get('ssh') or {}
ssh.pop('key_path', None)
if not ssh:
    repo.pop('ssh', None)
else:
    repo['ssh'] = ssh
if not repo:
    dev.pop('repo', None)
else:
    dev['repo'] = repo
if not dev:
    cfg.pop('dev', None)
else:
    cfg['dev'] = dev
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
"
            if [ $? -ne 0 ]; then
                if type print_message_box &>/dev/null; then
                    print_message_box "RED" "Error" "Write Failed" "Failed to remove dev.repo.ssh.key_path from .__ontobdc__/config.yaml"
                else
                    echo "Error: Failed to remove dev.repo.ssh.key_path from .__ontobdc__/config.yaml"
                fi
                exit 1
            fi

            if type print_message_box &>/dev/null; then
                print_message_box "GREEN" "Success" "SSH Key Removed" "Removed dev.repo.ssh.key_path from .__ontobdc__/config.yaml"
            else
                echo "Success: Removed dev.repo.ssh.key_path from .__ontobdc__/config.yaml"
            fi
            exit 0
        fi

        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Unknown Option" "Usage:\n  ontobdc dev repo --add-ssh-key <path>\n  ontobdc dev repo --rm-ssh-key"
        else
            echo "Error: Unknown option"
            echo "Usage: ontobdc dev repo --add-ssh-key <path>"
            echo "       ontobdc dev repo --rm-ssh-key"
        fi
        exit 1
    fi

    UNKNOWN_CMD="$1"
    CONTENT=""
    CONTENT="${CONTENT}Unknown command: ${UNKNOWN_CMD}\n\n"
    CONTENT="${CONTENT}  \033[37mUsage:\033[0m\n"
    CONTENT="${CONTENT}    \033[90montobdc dev <command> [args]\033[0m\n\n"
    CONTENT="${CONTENT}  \033[37mCommands:\033[0m\n"
    CONTENT="${CONTENT}    \033[36m--help\033[0m                               \033[90mShow this help\033[0m\n"
    CONTENT="${CONTENT}    \033[36m--enable-dev-tool\033[0m                    \033[90mEnable dev.tool in .__ontobdc__/config.yaml (must be passed alone)\033[0m\n"
    CONTENT="${CONTENT}    \033[36mcommit <message>\033[0m                     \033[90mCommit and push changes across repos\033[0m\n"
    CONTENT="${CONTENT}    \033[36mbranch\033[0m                             \033[90mList submodules and show git status (with branch)\033[0m\n"
    CONTENT="${CONTENT}    \033[36mbranch --create <name>\033[0m             \033[90mCreate and push branch across repos\033[0m\n"
    CONTENT="${CONTENT}    \033[36mcheckout <name>\033[0m                      \033[90mAlias for: branch --checkout <name>\033[0m\n"
    CONTENT="${CONTENT}  \033[37mNotes:\033[0m\n"
    CONTENT="${CONTENT}    \033[90mMost dev commands require \033[1;37mdev.tool: enabled\033[0;90m in .__ontobdc__/config.yaml.\033[0m\n"
    CONTENT="${CONTENT}    \033[90mRun: \033[1;37montobdc dev --enable-dev-tool\033[0;90m\033[0m\n"

    if type print_message_box &>/dev/null; then
        print_message_box "RED" "Error" "Dev Command Not Found" "$CONTENT"
    else
        echo -e "Error: Dev command not found: ${UNKNOWN_CMD}" 1>&2
        echo -e "$CONTENT" 1>&2
    fi
    exit 1
fi

source "${SCRIPT_DIR}/help.sh"
CONTENT="$(ontobdc_help_dev_content)"
CONTENT="   • Root directory: ${ROOT_DIR}\n\n${CONTENT}"

if type print_message_box &>/dev/null; then
    print_message_box "BLUE" "OntoBDC" "Dev" "$CONTENT"
else
    echo -e "$CONTENT"
fi
exit 0
