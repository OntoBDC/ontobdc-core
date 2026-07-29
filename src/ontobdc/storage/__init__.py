from pathlib import Path
from typing import Optional

from ontobdc.shared.adapter.config import ConfigDataAdapter


def get_storage_file(root_path: Optional[str] = None) -> str:
    if isinstance(root_path, str) and root_path.strip():
        return str(Path(root_path).expanduser().resolve() / ".__ontobdc__" / "storage.ttl")

    config_adapter: ConfigDataAdapter = ConfigDataAdapter()
    return str(config_adapter.config_dir / "storage.ttl")
