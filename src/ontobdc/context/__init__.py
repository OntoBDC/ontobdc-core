
from pathlib import Path
from typing import Optional
from ontobdc.shared.adapter.config import ConfigDataAdapter


def get_context_file() -> str:
    config_dir: Optional[Path] = ConfigDataAdapter().config_dir
    if not isinstance(config_dir, Path) or not config_dir.exists():
        raise ValueError("Project configuration directory could not be resolved.")

    return str(config_dir / "context.ttl")
