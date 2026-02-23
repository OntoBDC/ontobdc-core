DESCRIPTION="Infra: Stack git repository"
check() {
    return 0
    if [ -d "./stack/.git" ] || [ -f "./stack/.git" ]; then
        # Handle submodule .git file or directory
        cd ./stack || return 1
        REMOTE=$(git remote get-url origin 2>/dev/null)
        cd .. || return 1
        if [[ "$REMOTE" == "git@github.com:InfoBIM-Community/infobim-ifc.git" ]]; then
            return 0
        fi
    fi
    return 1
}

repair() {
    echo "Repairing stack git repository..."
    if [ -d "./stack" ]; then
        cd ./stack || return 1
        git remote set-url origin git@github.com:InfoBIM-Community/infobim-ifc.git
        cd .. || return 1
    else
        ./infobim install
    fi
}
