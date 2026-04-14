import os
import sys
import subprocess
from typing import Optional

from ontobdc.cli import get_root_dir
from ontobdc.storage import create_local_storage


def _get_arg_value(flag: str) -> str | None:
    args = sys.argv[1:]
    try:
        i = args.index(flag)
        if i + 1 < len(args) and not args[i + 1].startswith("-"):
            return args[i + 1]
    except ValueError:
        pass
    return None


def _message_box(level: str, title_type: str, title: str, message: str) -> None:
    try:
        from ontobdc.cli import get_message_box_script
    except Exception:
        print(message)
        return

    script = get_message_box_script()
    if script and os.path.isfile(script):
        subprocess.run(["bash", script, level, title_type, title, message], check=False)
    else:
        print(message)


def main() -> int:
    local_path: Optional[str] = _get_arg_value("--local")
    if local_path is None:
        local_path = ""

    if not local_path.strip().startswith("/"):
        local_path = os.path.join(get_root_dir(), local_path)

    local_path = os.path.abspath(local_path)
    if not os.path.exists(local_path):
        _message_box("RED", "Error", "Storage", f"Path does not exist:\n{local_path}")
        return 1
    if not os.path.isdir(local_path):
        _message_box("RED", "Error", "Storage", f"Path is not a directory:\n{local_path}")
        return 1

    ret = create_local_storage(local_path)
    if ret != 0:
        return ret

    _message_box("GREEN", "Success", "Storage", f"Storage path validated:\n{local_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
