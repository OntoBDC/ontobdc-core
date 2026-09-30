from typing import ClassVar, Optional
from pathlib import Path

from ontobdc.shared.adapter.config import ConfigDataAdapter


class StorageFileLocator:
    """
    Resolves the path of the storage graph file.
    """
    FILE_NAME: ClassVar[str] = "storage.ttl"
    MARKER_DIR_NAME: ClassVar[str] = ".__ontobdc__"

    @classmethod
    def resolve(cls, root_path: Optional[str] = None) -> str:
        """
        Path of the storage file, under the given root or the configured one.
        """
        if isinstance(root_path, str) and root_path.strip():
            return cls.for_root(root_path)

        return cls.configured()

    @classmethod
    def for_root(cls, root_path: str) -> str:
        root: Path = Path(root_path).expanduser().resolve()

        return str(root / cls.MARKER_DIR_NAME / cls.FILE_NAME)

    @classmethod
    def configured(cls) -> str:
        config_adapter: ConfigDataAdapter = ConfigDataAdapter()

        return str(config_adapter.config_dir / cls.FILE_NAME)
