import os
from typing import Optional

from ontobdc.cli import get_config_dir


def get_context_file() -> str:
    config_dir: Optional[str] = get_config_dir()
    if not isinstance(config_dir, str) or not config_dir.strip():
        raise ValueError("Project configuration directory could not be resolved.")

    return os.path.join(config_dir, "context.ttl")
