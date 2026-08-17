import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment.error import AttachRollbackError


class AttachmentTransactionCoordinator:
    """Coordinate the backup, rollback, and atomic-write side of attachment.

    Responsibilities:

    * Snapshotting the relevant portion of the CLI execution context so a
      failed attachment can be rolled back deterministically.
    * Creating and discarding per-attachment backup directories (one copy
      per container / dataset / storage graph touched by the operation).
    * Restoring all files from a backup directory on failure, together
      with the matching CLI parameter snapshot.
    * Performing the temp-file + replace pattern used by the
      multi-graph writer so a partial write can never be observed on disk.

    Context, plan, and plan-parameter are supplied once to the constructor
    so the first four operations do not require repeating them on every
    call. The pure graph writer is intentionally exposed as a classmethod
    because it has no dependency on CLI state.
    """

    _CONTEXT_PARAMETER_NAMES: tuple[str, ...] = (
        "container",
        "container_id",
        "container_path",
        "dataset_path",
        "container_update_completed",
        "container_html_view_updated",
    )

    def __init__(
        self,
        context: CliContextPort,
        plan: Dict[str, Any],
        plan_parameter: str,
    ) -> None:
        self._context: CliContextPort = context
        self._plan: Dict[str, Any] = plan
        self._plan_parameter: str = plan_parameter

    @classmethod
    def snapshot_context(
        cls,
        context: CliContextPort,
    ) -> Dict[str, Any]:
        return {
            name: context.get_parameter_value(name)
            for name in cls._CONTEXT_PARAMETER_NAMES
        }

    def ensure_backup(self) -> None:
        backups: Any = self._plan.get("backups")
        if isinstance(backups, list) and backups:
            return
        backup_dir: Path = Path(tempfile.mkdtemp(prefix="ontobdc-attach-"))
        source_files: List[Path] = [
            Path(self._plan["container_file"]),
            Path(self._plan["storage_file"]),
            *[Path(dataset["file"]) for dataset in self._plan["datasets"]],
        ]
        backup_entries: List[Dict[str, str]] = []
        try:
            for index, source in enumerate(source_files):
                backup: Path = backup_dir / f"{index:04d}-{source.name}"
                shutil.copy2(source, backup)
                backup_entries.append(
                    {"source": str(source), "backup": str(backup)}
                )
        except Exception as error:
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise AttachRollbackError(
                f"Could not create attachment backup: {error}"
            ) from error
        self._plan["backup_dir"] = str(backup_dir)
        self._plan["backups"] = backup_entries
        self._context.set_parameter_value(self._plan_parameter, self._plan)

    def discard_backup(self) -> None:
        backup_dir_value: str = str(self._plan.get("backup_dir") or "").strip()
        if backup_dir_value:
            shutil.rmtree(Path(backup_dir_value), ignore_errors=True)
        self._plan.pop("backup_dir", None)
        self._plan.pop("backups", None)

    def restore_context_snapshot(self) -> None:
        snapshot: Any = self._plan.get("context_snapshot")
        if not isinstance(snapshot, dict):
            return
        for parameter_name in self._CONTEXT_PARAMETER_NAMES:
            value: Any = snapshot.get(parameter_name)
            if value is None:
                self._context.delete_parameter(parameter_name)
            else:
                self._context.set_parameter_value(parameter_name, value)

    def restore(self) -> None:
        backups: Any = self._plan.get("backups")
        if not isinstance(backups, list) or not backups:
            return
        failures: List[str] = []
        for entry in backups:
            try:
                source: Path = Path(entry["source"])
                backup: Path = Path(entry["backup"])
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, source)
            except Exception as error:
                failures.append(f"{entry}: {error}")
        if failures:
            raise AttachRollbackError("; ".join(failures))
        self.restore_context_snapshot()
        self.discard_backup()
        self._context.set_parameter_value(self._plan_parameter, self._plan)

    @classmethod
    def write_graphs_transactionally(
        cls,
        payloads: Dict[Path, Graph],
    ) -> None:
        serialized: Dict[Path, bytes] = {
            path: graph.serialize(format="turtle", encoding="utf-8")
            for path, graph in payloads.items()
        }
        temporary_paths: Dict[Path, Path] = {}
        original_bytes: Dict[Path, Optional[bytes]] = {
            path: path.read_bytes() if path.is_file() else None
            for path in serialized
        }
        try:
            for path, content in serialized.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary: Path = path.with_name(f".{path.name}.attach.tmp")
                temporary.write_bytes(content)
                temporary_paths[path] = temporary
            for path, temporary in temporary_paths.items():
                temporary.replace(path)
        except Exception as error:
            rollback_failures: List[str] = []
            for path, content in original_bytes.items():
                try:
                    if content is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(content)
                except Exception as rollback_error:
                    rollback_failures.append(f"{path}: {rollback_error}")
            if rollback_failures:
                raise AttachRollbackError(
                    "; ".join(rollback_failures)
                ) from error
            raise
        finally:
            for temporary in temporary_paths.values():
                temporary.unlink(missing_ok=True)
