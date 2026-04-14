
import os
import json
import subprocess
from ontobdc.cli import get_config_dir
from ontobdc.storage.adapter.storage import StorageIndexAdapter


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


def has_storage_index() -> bool:
    storage_rdf = os.path.join(get_config_dir(), StorageIndexAdapter.INDEX_FILE)
    return os.path.isfile(storage_rdf)


def create_storage_index(storage_path: str) -> int:
    if has_storage_index():
        _message_box("YELLOW", "Warning", "Storage", f"Storage index already exists:\n{storage_path}")
        return 2

    try:
        storage_index: StorageIndexAdapter = StorageIndexAdapter.create()
        storage_index.add(storage_path, save_action = storage_index.save)
    except Exception as e:
        _message_box("RED", "Error", "Storage", f"Failed to create storage index:\n{storage_path}\n{e}")
        return 1

    return 0


def create_storage(storage_path: str) -> int:
    list_script = os.path.join(os.path.dirname(__file__), "list.py")
    out = subprocess.run(
        ["python3", list_script, storage_path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=os.environ.copy(),
    ).stdout.strip()

    try:
        existing = json.loads(out) if out else []
    except Exception:
        existing = []

    if isinstance(existing, list) and len(existing) > 0:
        _message_box("YELLOW", "Warning", "Storage", f"Storage already initialized at:\n{storage_path}")
        return 2

    return create_storage_index(storage_path)


def create_local_storage(local_path: str) -> int:
    return create_storage(local_path)
