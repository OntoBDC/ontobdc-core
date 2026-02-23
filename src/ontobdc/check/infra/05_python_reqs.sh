DESCRIPTION="Infra: Python Requirements"

REQ_FILE="$(dirname "${BASH_SOURCE[0]}")/requirements.txt"

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

    if [ "$ENGINE" != "colab" ] && [[ ! -f "venv/bin/python3" ]]; then
        return 1
    fi
    
    # If requirements file doesn't exist, fail
    if [[ ! -f "$REQ_FILE" ]]; then
        return 1
    fi

    PYTHON_CMD="./venv/bin/python3"
    if [ "$ENGINE" = "colab" ]; then
        PYTHON_CMD="python3"
    fi

    # Use python to check installed packages
    $PYTHON_CMD -c "
import sys
import warnings
warnings.filterwarnings('ignore')
try:
    import pkg_resources
except ImportError:
    # setuptools not installed
    sys.exit(1)

try:
    with open('$REQ_FILE', 'r') as f:
        # Filter empty lines and comments
        reqs = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    # Check if requirements are satisfied
    pkg_resources.require(reqs)
except Exception:
    sys.exit(1)
"
}

hotfix() {
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

    if [ "$ENGINE" != "colab" ] && [[ ! -f "venv/bin/python3" ]]; then
        echo "Virtual environment not found."
        return 1
    fi
    
    echo "Installing requirements..."
    PYTHON_CMD="./venv/bin/python3"
    if [ "$ENGINE" = "colab" ]; then
        PYTHON_CMD="python3"
    fi

    $PYTHON_CMD -m pip install -r "$REQ_FILE"
}
