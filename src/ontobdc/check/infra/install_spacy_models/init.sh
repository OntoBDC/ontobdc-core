DESCRIPTION="Infra: spaCy Language Models"
PYTHON_BIN="${PYTHON_BIN:-python3}"

get_script_dir() {
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

get_check_script() {
    echo "$(get_script_dir)/check.py"
}

check() {
    "${PYTHON_BIN}" "$(get_check_script)" check >/dev/null 2>&1
}

hotfix() {
    if ! "${PYTHON_BIN}" -m pip show spacy >/dev/null 2>&1; then
        "${PYTHON_BIN}" -m pip install spacy >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi

    MISSING_MODELS="$("${PYTHON_BIN}" "$(get_check_script)" missing-models 2>/dev/null)"
    if [ $? -ne 0 ]; then
        return 1
    fi

    if [ -z "$MISSING_MODELS" ]; then
        return 0
    fi

    while IFS= read -r model_name; do
        if [ -z "$model_name" ]; then
            continue
        fi

        "${PYTHON_BIN}" -m spacy download "$model_name" >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            return 1
        fi
    done <<EOF
$MISSING_MODELS
EOF

    return 0
}

repair() {
    hotfix
}
