from typing import Optional

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


def main(root_path: Optional[str] = None) -> int:
    try:
        directory = StorageBootstrap.get_ontobdc_directory(
            StorageBootstrap.get_init_root_path(root_path=root_path)
        )
        return 0 if directory.is_dir() else 1
    except Exception:
        return 1
