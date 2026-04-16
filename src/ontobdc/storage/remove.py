import sys
from typing import Optional

from ontobdc.storage import remove_storage


def _get_arg_value(flag: str) -> Optional[str]:
    args = sys.argv[1:]
    try:
        i = args.index(flag)
        if i + 1 < len(args) and not args[i + 1].startswith("-"):
            return args[i + 1]
    except ValueError:
        pass
    return None


def main() -> int:
    dataset_id = _get_arg_value("--remove")
    if not dataset_id:
        sys.stderr.write("Error: Usage: ontobdc storage --remove <dataset_id>\n")
        return 1

    return remove_storage(dataset_id)


if __name__ == "__main__":
    raise SystemExit(main())
