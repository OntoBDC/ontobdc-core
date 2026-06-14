DESCRIPTION="Infra: Venv Active"

check() {
    if [ -n "$VIRTUAL_ENV" ]; then
        return 0
    fi
    
    # Check if we are in a CI/CD environment or Colab where venv might not be used the same way
    if [ -d "/content" ]; then
        return 0
    fi

    return 1
}

hotfix() {
    # Try to activate venv if it exists in the current directory or parent
    if [ -f "venv/bin/activate" ]; then
        source "venv/bin/activate"
    elif [ -f "../venv/bin/activate" ]; then
        source "../venv/bin/activate"
    fi
}

repair() {
    hotfix
}
