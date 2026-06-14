DESCRIPTION="Infra: Python Requirements"

check() {
    # Check dependencies dynamically from pyproject.toml if it exists
    # If pyproject.toml is missing, assume dependencies are managed elsewhere (or none) and pass.
    
    python3 -c '
import sys, os, re
from importlib.metadata import distribution, PackageNotFoundError

if not os.path.exists("pyproject.toml"):
    sys.exit(0)

try:
    with open("pyproject.toml", "r") as f:
        content = f.read()

    # Find "dependencies = [...]" block (multiline supported by re.DOTALL)
    # Using (?m)^ to match start of line to avoid partial matches like "dev-dependencies"
    m = re.search(r"(?m)^dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not m:
        # If no dependencies section found, assume ok
        sys.exit(0)
    
    deps_block = m.group(1)
    # Extract strings (package names/specs)
    # Matches "package" or "package>=1.0" inside double quotes
    raw_deps = re.findall(r"\"([^\"]+)\"", deps_block)
    
    missing = []
    for d in raw_deps:
        # Strip version specifiers and extras to get distribution name
        # e.g. "package[extra]>=1.0" -> "package"
        pkg = re.split(r"[<>=!~;\[]", d)[0].strip()
        try:
            distribution(pkg)
        except PackageNotFoundError:
            missing.append(pkg)
            
    if missing:
        # print(f"Missing dependencies: {", ".join(missing)}")
        sys.exit(1)

except Exception:
    # If parsing fails, maybe assume failure or pass? 
    # Let"s be strict and fail check if we can"t parse but file exists
    sys.exit(1)
' >/dev/null 2>&1
}

hotfix() {
    # Try to install dependencies if check failed
    
    if [ -f "pyproject.toml" ]; then
        # Dynamically extract dependencies from pyproject.toml
        DEPS=$(python3 -c '
import sys, re
try:
    with open("pyproject.toml", "r") as f:
        content = f.read()
    m = re.search(r"(?m)^dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if m:
        deps_block = m.group(1)
        # Extract strings (package names/specs)
        # Matches "package" or "package>=1.0" inside double quotes
        raw_deps = re.findall(r"\"([^\"]+)\"", deps_block)
        print(" ".join(raw_deps))
except:
    sys.exit(1)
')
        if [ $? -eq 0 ] && [ -n "$DEPS" ]; then
            pip install $DEPS > /dev/null 2>&1
            return $?
        else
            # Fallback to standard pip install if extraction fails
            pip install . > /dev/null 2>&1
            return $?
        fi
        
    elif [ -f "requirements.txt" ]; then
        pip install -r requirements.txt > /dev/null 2>&1
        return $?
    fi
    
    # No configuration found
    return 1
}

repair() {
    hotfix
}
