DESCRIPTION="Infra: Engine Installed"

check() {
    CONFIG_FILE=".__ontobdc__/config.yaml"
    
    # Try parent directory if not found in CWD (workspace support)
    if [ ! -f "$CONFIG_FILE" ]; then
         if [ -f "../.__ontobdc__/config.yaml" ]; then
             CONFIG_FILE="../.__ontobdc__/config.yaml"
         elif [ -f "../../.__ontobdc__/config.yaml" ]; then
             CONFIG_FILE="../../.__ontobdc__/config.yaml"
         else
             return 2
         fi
    fi

    if [ ! -f "$CONFIG_FILE" ]; then
        return 2
    fi
    
    # Check for engine definition
    # Use awk to get the value after "engine:" and trim whitespace
    ENGINE=$(grep "^engine:" "$CONFIG_FILE" | awk '{print $2}')
    
    if [ -z "$ENGINE" ]; then
        return 2
    fi
    
    # Validate against allowed engines in config.json
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # .../infra/is_engine_installed/../../config.json -> .../check/config.json
    CHECK_CONFIG="${SCRIPT_DIR}/../../config.json"
    
    if [ ! -f "$CHECK_CONFIG" ]; then
        return 2
    fi
    
    # Check if engine is in allowed list (config.engines list in json)
    IS_VALID=$(python3 -c "import json; import sys; 
try:
    with open('$CHECK_CONFIG') as f: data = json.load(f);
    # Access config -> engines list
    engines = data.get('config', {}).get('engines', [])
    if '$ENGINE' in engines: print('true')
    else: print('false')
except Exception as e: print('false')")

    if [ "$IS_VALID" == "true" ]; then
        return 0
    else
        return 2
    fi
}

hotfix() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # 1. Colab Hotfix
    if [ -d "/content" ]; then
        IS_COLAB_SCRIPT="${SCRIPT_DIR}/../is_colab/init.sh"
        if [ -f "$IS_COLAB_SCRIPT" ]; then
            (
                source "$IS_COLAB_SCRIPT"
                hotfix
            )
            return $?
        fi
    fi
    
    # 2. Venv Hotfix
    # Check if venv is active using is_venv_active logic
    IS_VENV_SCRIPT="${SCRIPT_DIR}/../is_venv_active/init.sh"
    if [ -f "$IS_VENV_SCRIPT" ]; then
        # We run check() from is_venv_active to see if we are in a venv
        (
            source "$IS_VENV_SCRIPT"
            if check; then
                # If check passes (we are in a venv), we should configure engine: venv
                
                # Create config file
                mkdir -p .__ontobdc__
                CONFIG_FILE=".__ontobdc__/config.yaml"
                
                # Update config file
                if [ -f "$CONFIG_FILE" ]; then
                    grep -v "engine:" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
                    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
                fi
                
                echo "engine: venv" >> "$CONFIG_FILE"
                return 0
            fi
        )
        return $?
    fi
    
    # If not colab and not venv, we cannot hotfix automatically
    return 1
}

repair() {
    # Try hotfix first
    if hotfix; then
        return 0
    fi

    # Fatal error if hotfix failed (i.e. not in Colab or file creation failed)
    echo ""
    if type print_message_box &>/dev/null; then
        print_message_box "$RED" "FATAL ERROR" "Invalid Engine Configuration" "The 'engine' specified in ontobdc.yaml is invalid or missing.\n\nValid engines are: venv, colab\n\nPlease check your configuration file."
    else
        echo -e "${RED}FATAL ERROR: Invalid Engine Configuration${RESET}"
        echo "The 'engine' specified in ontobdc.yaml is invalid or missing."
    fi
    exit 1
}
