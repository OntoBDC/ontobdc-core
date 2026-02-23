DESCRIPTION="Infra: Python 3.11+"
check() {
    if command -v python3 &>/dev/null; then
        # Get version in format X.Y
        VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        # Check if version >= 3.11
        if awk -v ver="$VERSION" 'BEGIN { if (ver >= 3.11) exit 0; else exit 1; }'; then
            return 0
        fi
    fi
    return 1
}

repair() {
    print_message_box "$YELLOW" "Warning" "Manual Action Required" "Please install ${CYAN}Python 3.11+${RESET} manually.\nDownload: https://www.python.org/downloads/"
    exit 1
}
