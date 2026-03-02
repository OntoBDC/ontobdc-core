DESCRIPTION="Infra: Colab Environment"

check() {
    # If we are not in colab environment (no /content dir), this check is irrelevant/skipped by logic in check.sh?
    # Actually, check.sh uses engine specific checks. If ENGINE=colab, this runs.
    # If we are here, we expect to be in colab.
    
    # But wait, check.sh heuristics:
    # if [ -d "/content" ]; then ENGINE="colab"; fi
    
    # If we are in colab, we want to ensure config exists?
    # Or is this check meant to verify we ARE in colab?
    
    if [ ! -d "/content" ]; then
        # Not in colab, so we can't be "is_colab"
        return 1
    fi

    # Check if config exists and has engine: colab
    if [ -f "/content/config/ontobdc.yaml" ]; then
        if grep -q "engine: colab" "/content/config/ontobdc.yaml"; then
            return 0
        fi
    fi
    
    return 1
}

hotfix() {
    if [ -d "/content" ]; then
        mkdir -p /content/config
        local config_file="/content/config/ontobdc.yaml"
        
        if [ -f "$config_file" ]; then
            # Remove existing engine definition if any
            # Using temporary file to avoid issues
            grep -v "engine:" "$config_file" > "${config_file}.tmp"
            mv "${config_file}.tmp" "$config_file"
        fi
        
        # Append engine: colab
        echo "engine: colab" >> "$config_file"
        return 0
    fi
    return 1
}

repair() {
    hotfix
}
