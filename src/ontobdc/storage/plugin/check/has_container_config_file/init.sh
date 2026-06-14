DESCRIPTION="Storage: Container Configuration File"

check() {
    "${PYTHON_BIN}" "${SCRIPT_DIR}/check.py" check
    return $?
}

hotfix() {
    "${PYTHON_BIN}" "${SCRIPT_DIR}/hotfix.py"
    return $?
}

repair() {
    hotfix
}