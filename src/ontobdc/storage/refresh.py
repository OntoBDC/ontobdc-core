
import sys
from typing import Optional
from ontobdc.storage import refresh_storage


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
    dataset_id = _get_arg_value("--refresh")
    return refresh_storage(dataset_id)


if __name__ == "__main__":
    raise SystemExit(main())

