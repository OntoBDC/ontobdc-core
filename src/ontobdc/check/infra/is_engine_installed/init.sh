DESCRIPTION="Infra: Engine Installed"

check() {
    # Check if we are in Colab, then check specific config path
    if [ -d "/content" ]; then
        CONFIG_FILE="/content/config/ontobdc.yaml"
    else
        # If local, try to find config relative to execution or script
        if [ -f "config/ontobdc.yaml" ]; then
            CONFIG_FILE="config/ontobdc.yaml"
        elif [ -f "../config/ontobdc.yaml" ]; then
             CONFIG_FILE="../config/ontobdc.yaml"
        elif [ -f "../../config/ontobdc.yaml" ]; then
             CONFIG_FILE="../../config/ontobdc.yaml"
        else
             # If we can't find config file in standard places
             # This is a FATAL error because we don't know the engine
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
    # Try to determine if we are in Colab using the logic from is_colab module
    # We can source the is_colab module to use its check function logic, but simplified:
    if [ -d "/content" ]; then
        # We are likely in Colab, let's try to fix it by creating the config
        mkdir -p /content/config
        local config_file="/content/config/ontobdc.yaml"
        
        if [ -f "$config_file" ]; then
            # Remove existing engine definition if any
            grep -v "engine:" "$config_file" > "${config_file}.tmp"
            mv "${config_file}.tmp" "$config_file"
        fi
        
        # Append engine: colab
        echo "engine: colab" >> "$config_file"
        return 0
    fi
    
    # If not colab, we cannot hotfix automatically
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
