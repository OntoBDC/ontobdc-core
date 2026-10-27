from pathlib import Path
from typing import Any, Dict

import yaml

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class InitContainerFiles:
    """
    The files of the .__ontobdc__ directory an init brings to a healthy state.
    """

    CONFIG_FILE_NAME: str = "config.yaml"

    @classmethod
    def root(cls, root_path: str) -> Path:
        return Path(root_path).expanduser().resolve()

    @classmethod
    def config_file(cls, root_path: str) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(cls.root(root_path))
            / cls.CONFIG_FILE_NAME
        )

    @classmethod
    def read_config(cls, root_path: str) -> Dict[str, Any]:
        config_file: Path = cls.config_file(root_path)
        if not config_file.is_file():
            return {}

        loaded: Any = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}

    @classmethod
    def write_config(cls, root_path: str, config: Dict[str, Any]) -> None:
        config_file: Path = cls.config_file(root_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            yaml.safe_dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
