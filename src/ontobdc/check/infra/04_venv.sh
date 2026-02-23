DESCRIPTION="Infra: Virtual Environment (venv)"

check() {
    ENGINE="venv"
    if [[ -f "config/infobim.yaml" ]]; then
        ENGINE=$(awk '
            /^[[:space:]]*-[[:space:]]*install:/ { in_inst=1; next }
            /^[[:space:]]*-[[:space:]]*[^[:space:]]/ && in_inst { exit }
            in_inst && $1 ~ /engine:/ {
                for (i=2; i<=NF; i++) {
                    printf "%s%s", $i, (i<NF?" ":"")
                }
                print ""
                exit
            }
        ' "config/infobim.yaml")
        [[ -z "$ENGINE" ]] && ENGINE="venv"
    fi

    if [ "$ENGINE" = "colab" ]; then
        DESCRIPTION="Infra: Virtual Environment (Skipped: Colab Mode)"
        return 0
    fi

    if [[ -d "venv" && -f "venv/bin/activate" ]]; then
        return 0
    fi
    return 1
}

repair() {
    ENGINE="venv"
    if [[ -f "config/infobim.yaml" ]]; then
        ENGINE=$(awk '
            /^[[:space:]]*-[[:space:]]*install:/ { in_inst=1; next }
            /^[[:space:]]*-[[:space:]]*[^[:space:]]/ && in_inst { exit }
            in_inst && $1 ~ /engine:/ {
                for (i=2; i<=NF; i++) {
                    printf "%s%s", $i, (i<NF?" ":"")
                }
                print ""
                exit
            }
        ' "config/infobim.yaml")
        [[ -z "$ENGINE" ]] && ENGINE="venv"
    fi

    if [ "$ENGINE" = "colab" ]; then
        echo "Colab detected. Skipping venv creation."
        return 0
    fi

    echo "Creating virtual environment..."
    if command -v python3 &>/dev/null; then
        python3 -m venv venv
    else
        echo "Python 3 is not installed. Cannot create venv."
    fi
}
