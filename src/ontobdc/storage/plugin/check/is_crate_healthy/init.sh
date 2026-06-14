DESCRIPTION="Storage: RO-Crate Health"

check() {
    "${PYTHON_BIN}" "${SCRIPT_DIR}/check.py"
    return $?
}

hotfix() {
    "${PYTHON_BIN}" "${SCRIPT_DIR}/hotfix.py"
    return $?
}

repair() {
    hotfix
}
