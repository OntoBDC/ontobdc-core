
import os
import json
import builtins
import sys
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
    try:
        if has_storage_index():
            storage_index: StorageIndexAdapter = StorageIndexAdapter()
        else:
            storage_index: StorageIndexAdapter = StorageIndexAdapter.create()

        storage_index.add(storage_path, save_action = storage_index.save)
    except Exception as e:
        _message_box("RED", "Error", "Storage", f"Failed to create storage index:\n{storage_path}\n{e}")
        return 1

    return 0


def create_storage(storage_path: str) -> int:
    list_script = os.path.join(os.path.dirname(__file__), "list.py")
    py_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{py_root}:{env.get('PYTHONPATH', '')}".rstrip(":")
    out = subprocess.run(
        [sys.executable, list_script, storage_path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    ).stdout.strip()

    try:
        existing = json.loads(out) if out else []
    except Exception:
        existing = []

    if isinstance(existing, builtins.list) and len(existing) > 0:
        _message_box("YELLOW", "Warning", "Storage", f"Storage already initialized at:\n{storage_path}")
        return 2

    return create_storage_index(storage_path)


def create_local_storage(local_path: str) -> int:
    return create_storage(local_path)


def remove_storage(dataset_id: str) -> int:
    if not has_storage_index():
        _message_box("YELLOW", "Warning", "Storage", "No storage has been initialized yet.")
        return 2

    try:
        storage_index: StorageIndexAdapter = StorageIndexAdapter()
        removed = storage_index.remove(dataset_id, save_action=storage_index.save)
    except Exception as e:
        _message_box("RED", "Error", "Storage", f"Failed to remove dataset:\n{dataset_id}\n{e}")
        return 1

    if not removed:
        _message_box("YELLOW", "Warning", "Storage", f"Dataset not found:\n{dataset_id}")
        return 2

    _message_box("GREEN", "Success", "Storage", f"Dataset removed:\n{dataset_id}")
    return 0


def refresh_storage(dataset_id: str | None = None) -> int:
    if not has_storage_index():
        _message_box("YELLOW", "Warning", "Storage", "No storage has been initialized yet.")
        return 2

    try:
        storage_index: StorageIndexAdapter = StorageIndexAdapter()
        if dataset_id and not storage_index.has_dataset(dataset_id):
            _message_box("YELLOW", "Warning", "Storage", f"Dataset not found:\n{dataset_id}")
            return 2
        refreshed = storage_index.refresh(dataset_id, save_action=storage_index.save)
    except Exception as e:
        target = dataset_id if dataset_id else "all"
        _message_box("RED", "Error", "Storage", f"Failed to refresh storage:\n{target}\n{e}")
        return 1

    if refreshed == 0:
        _message_box("GRAY", "Info", "Storage", "No changes detected.")
        return 0

    _message_box("GREEN", "Success", "Storage", f"Storage refreshed.\nDatasets updated: {refreshed}")
    return 0
