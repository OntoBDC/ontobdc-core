import sys
import subprocess
from importlib import resources


def main() -> None:
    script_dir = resources.files("ontobdc")
    script_path = script_dir / "ontobdc.sh"
    if not script_path.exists():
        raise FileNotFoundError(f"ontobdc.sh not found at {script_path}")
    args = [str(script_path)] + sys.argv[1:]
    result = subprocess.run(args)
    raise SystemExit(result.returncode)
