import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from rocrate.rocrate import ROCrate

from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.domain.model.file_history import DatasetHistoryEntry, FileHistory
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _previous_crate(container_path: Path) -> Dict[str, Any]:
    """The crate that is there; nothing when there is no crate, or it cannot be read."""
    crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(container_path)
    try:
        crate: Any = json.loads(crate_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return crate if isinstance(crate, dict) else {}


def _write_crate_manifest(marker_path: Path, container_path: Path, file_ids: List[str]) -> None:
    files: ContainerFileRepository = ContainerFileRepository(container_path)
    crate: ROCrate = ROCrate(gen_preview=False)
    # What the container knew of its files before is kept: the crate is written again, the history is not lost.
    before: Dict[str, Any] = _previous_crate(container_path)
    previous: Dict[str, FileHistory] = CrateFileHistory.read_all(before)
    owners: Dict[str, str] = CrateFileHistory.owners(before)
    node_histories: Dict[str, FileHistory] = CrateFileHistory.node_histories(before)
    # The history of the whole container keeps the entries of the files that are gone, and the ones of the nodes this crate drops.
    dataset_entries: List[DatasetHistoryEntry] = CrateFileHistory.dataset_entries_of(before) if before else []

    on_disk: Dict[str, Any] = {}
    for file_id in file_ids:
        properties = files.properties(file_id)
        if properties is not None:
            # A file that vanished between the directory walk and the serialization is dropped (a synced
            # folder propagating a delete): the manifest converges to the on-disk truth.
            on_disk[file_id] = properties

    # A file named by an identifier is one node, whatever the number of paths it is at (a copy is the same file).
    grouped: Dict[str, List[str]] = {}
    for file_id in on_disk:
        owner: Optional[str] = owners.get(file_id)
        if owner is not None and CrateFileHistory.is_identifier(owner):
            grouped.setdefault(owner, []).append(file_id)

    histories: Dict[str, FileHistory] = {}
    identifiers: Dict[str, str] = {}
    written: Dict[str, str] = {}
    for owner, paths in grouped.items():
        history: FileHistory = node_histories.get(owner, FileHistory())
        current: Optional[Any] = history.current()
        primary: str = current.relative_path if current is not None and current.relative_path in paths else sorted(paths)[0]
        for path in sorted(paths):
            history = CrateFileHistory.history_of(files, path, history)
        histories[primary] = CrateFileHistory.end_missing(history, set(paths))
        identifiers[primary] = owner
        for path in paths:
            written[path] = primary

    for file_id, properties in on_disk.items():
        if file_id in written and written[file_id] != file_id:
            continue
        if file_id not in written:
            histories[file_id] = CrateFileHistory.history_of(files, file_id, previous.get(file_id, FileHistory()))
        crate.add_file(
            source=None,
            dest_path=file_id,
            properties=properties,
        )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"No source for .*")
        crate.write(marker_path)

    # The history is a list of items without identity of their own, which the library does not write:
    # it goes into the document it wrote, in the node of each file.
    # What the crate that was there said is kept: the identifier of each file that is still there, and
    # the history of the whole container, with the entries of the files that are gone.
    CrateFileHistory.save(
        StorageBootstrap.get_container_crate_metadata_file_path(container_path),
        histories,
        identifiers=identifiers,
        dataset_entries=dataset_entries,
    )


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if check_container_storage_index_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    marker_path: Path = StorageBootstrap.ensure_ontobdc_directory(resolved_container_path)
    file_ids: List[str] = ContainerFileRepository(resolved_container_path).list()
    _write_crate_manifest(marker_path, resolved_container_path, file_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
