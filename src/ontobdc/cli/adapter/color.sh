# Define colors

print_text_in_color() {
    local COLOR="$1"
    local RESET='\033[0m'
    local BOLD='\033[1m'

    case "$COLOR" in
        "GRAY")
            COLOR='\033[90m' ;;
        "WHITE")
            COLOR='\033[37m' ;;
        "RED")
            COLOR='\033[31m' ;;
        "GREEN")
            COLOR='\033[32m' ;;
        "YELLOW")
            COLOR='\033[33m' ;;
        "BLUE")
            COLOR='\033[34m' ;;
        "CYAN")
            COLOR='\033[36m';;
        *)
            return 1;;
    esac

    echo "${COLOR}${2}${RESET}"

    return 0
}