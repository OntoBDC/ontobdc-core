DESCRIPTION="Infra: Python Requirements"

check() {
    # Instead of 'pip check' which complains about EVERYTHING in the environment (e.g. Colab pre-installed packages),
    # we specifically check if our critical dependencies are importable.
    # Critical deps: rich, yaml (PyYAML), numpy, datapackage
    if python3 -c "import rich, yaml, numpy, datapackage" >/dev/null 2>&1; then
        return 0
    else
        # If imports fail, try to be more specific or return failure
        return 1
    fi
}

hotfix() {
    # Try to install dependencies if check failed
    
    # If we are in development mode (source checkout)
    if [ -f "pyproject.toml" ]; then
        pip install -e . > /dev/null 2>&1
        return $?
    elif [ -f "requirements.txt" ]; then
        pip install -r requirements.txt > /dev/null 2>&1
        return $?
    fi
    
    # If we are in installed mode (no source files), try to fix by reinstalling the package itself?
    # Or try to install the known dependencies manually?
    # Let's try to install the critical ones if they are missing
    pip install rich PyYAML numpy datapackage > /dev/null 2>&1
    return $?
}

repair() {
    hotfix
}
