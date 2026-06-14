DESCRIPTION="Infra: Entity Framework Ready"

resolve_root_dir() {
    local py_root
    py_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"

    PYTHONPATH="${py_root}:${PYTHONPATH:-}" \
        python3 -c "from ontobdc.cli import get_root_dir; r=get_root_dir(); print(r or '')" 2>/dev/null
}

check() {
    local ROOT_DIR
    ROOT_DIR="$(resolve_root_dir)" || true

    if [ -z "${ROOT_DIR:-}" ]; then
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "Entity Framework Not Ready" "Missing .__ontobdc__ directory.\n\nRun from the project root:\n  ontobdc check --repair"
        else
            echo "Error: Missing .__ontobdc__ directory. Run 'ontobdc check --repair' from the project root."
        fi
        return 1
    fi

    local missing=()
    local entity_rdf="$ROOT_DIR/.__ontobdc__/entity.rdf"
    local dir_entity="$ROOT_DIR/.__ontobdc__/ontology/entity"
    local dir_container="$ROOT_DIR/.__ontobdc__/ontology/container"
    local dir_event="$ROOT_DIR/.__ontobdc__/payload/event"
    local dir_data="$ROOT_DIR/.__ontobdc__/payload/data"

    if [ ! -f "$entity_rdf" ]; then
        missing+=(".__ontobdc__/entity.rdf")
    fi
    if [ ! -d "$dir_entity" ]; then
        missing+=(".__ontobdc__/ontology/entity/")
    fi
    if [ ! -d "$dir_container" ]; then
        missing+=(".__ontobdc__/ontology/container/")
    fi
    if [ ! -d "$dir_event" ]; then
        missing+=(".__ontobdc__/payload/event/")
    fi
    if [ ! -d "$dir_data" ]; then
        missing+=(".__ontobdc__/payload/data/")
    fi

    if [ "${#missing[@]}" -ne 0 ]; then
        return 1
    fi

    local iso_container_rdf="$dir_container/Container.rdf"
    local iso_linkset_rdf="$dir_container/Linkset.rdf"

    if [ ! -f "$iso_container_rdf" ]; then
        missing+=(".__ontobdc__/ontology/container/Container.rdf")
    fi
    if [ ! -f "$iso_linkset_rdf" ]; then
        missing+=(".__ontobdc__/ontology/container/Linkset.rdf")
    fi

    if [ "${#missing[@]}" -ne 0 ]; then
        return 1
    fi

    return 0
}
hotfix() {
    local ROOT_DIR
    ROOT_DIR="$(resolve_root_dir)" || true
    if [ -z "${ROOT_DIR:-}" ]; then
        ROOT_DIR="$(pwd)"
    fi

    mkdir -p "$ROOT_DIR/.__ontobdc__/ontology/entity" >/dev/null 2>&1
    mkdir -p "$ROOT_DIR/.__ontobdc__/ontology/container" >/dev/null 2>&1
    mkdir -p "$ROOT_DIR/.__ontobdc__/payload/event" >/dev/null 2>&1
    mkdir -p "$ROOT_DIR/.__ontobdc__/payload/data" >/dev/null 2>&1
    echo '<?xml version="1.0" encoding="utf-8"?>' > "$ROOT_DIR/.__ontobdc__/entity.rdf" 2>/dev/null
    echo '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"></rdf:RDF>' >> "$ROOT_DIR/.__ontobdc__/entity.rdf" 2>/dev/null

    local iso_dir="$ROOT_DIR/.__ontobdc__/ontology/container"
    local iso_container_rdf="$iso_dir/Container.rdf"
    local iso_linkset_rdf="$iso_dir/Linkset.rdf"

    download_file() {
        local url="$1"
        local out="$2"
        if [ -f "$out" ]; then
            return 0
        fi
        if command -v curl >/dev/null 2>&1; then
            local err
            err="$(curl -fsSL "$url" -o "$out" 2>&1)"
            local rc=$?
            if [ $rc -ne 0 ]; then
                rm -f "$out" >/dev/null 2>&1 || true
                if type log_line &>/dev/null; then
                    log_line "ERROR" "Failed to download ISO 21597 ontology" "url=$url" "error=$err"
                else
                    echo "ERROR: Failed to download ISO 21597 ontology: $url"
                    echo "ERROR: $err"
                fi
                return $rc
            fi
            return 0
        fi
        if command -v wget >/dev/null 2>&1; then
            local err
            err="$(wget -qO "$out" "$url" 2>&1)"
            local rc=$?
            if [ $rc -ne 0 ]; then
                rm -f "$out" >/dev/null 2>&1 || true
                if type log_line &>/dev/null; then
                    log_line "ERROR" "Failed to download ISO 21597 ontology" "url=$url" "error=$err"
                else
                    echo "ERROR: Failed to download ISO 21597 ontology: $url"
                    echo "ERROR: $err"
                fi
                return $rc
            fi
            return 0
        fi
        python3 -c "import sys, urllib.request
url=sys.argv[1]
out=sys.argv[2]
try:
    urllib.request.urlretrieve(url, out)
except Exception as e:
    print(str(e), file=sys.stderr)
    raise
" "$url" "$out"
    }

    download_file "https://standards.iso.org/iso/21597/-1/ed-1/en/Container.rdf" "$iso_container_rdf" || {
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "ISO Ontology Download Failed" "Could not download ISO 21597 ontology files.\n\nCheck your internet/DNS or place these files manually in:\n  .__ontobdc__/ontology/container/\n\nRequired:\n  - Container.rdf\n  - Linkset.rdf"
        fi
        return 1
    }
    download_file "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset.rdf" "$iso_linkset_rdf" || {
        if type print_message_box &>/dev/null; then
            print_message_box "RED" "Error" "ISO Ontology Download Failed" "Could not download ISO 21597 ontology files.\n\nCheck your internet/DNS or place these files manually in:\n  .__ontobdc__/ontology/container/\n\nRequired:\n  - Container.rdf\n  - Linkset.rdf"
        fi
        return 1
    }

    return 0
}

repair() {
    hotfix
}
