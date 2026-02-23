DESCRIPTION="Infra: Stack structure"
check() {
    if [[ -d "./stack" && -f "./stack/infobim.sh" ]]; then
        return 0
    fi
    return 1
}

repair() {
    print_message_box "$YELLOW" "Warning" "Manual Action Required" "Please run ${CYAN}./infobim install${RESET} manually to install the stack."
    exit 1
}
