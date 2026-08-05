import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment_error import AttachRollbackError


_CONTEXT_PARAMETER_NAMES = (
    "container",
    "container_id",
    "container_path",
    "dataset_path",
    "container_update_completed",
    "container_html_view_updated",
)


def snapshot_context(context: CliContextPort) -> Dict[str, Any]:
    return {
        name: context.get_parameter_value(name)
        for name in _CONTEXT_PARAMETER_NAMES
    }


def ensure_attachment_backup(
    context: CliContextPort,
    plan: Dict[str, Any],
    plan_parameter: str,
) -> None:
    backups = plan.get("backups")
    if isinstance(backups, list) and backups:
        return
    backup_dir = Path(tempfile.mkdtemp(prefix="ontobdc-attach-"))
    source_files = [
        Path(plan["container_file"]),
        Path(plan["storage_file"]),
        *[Path(dataset["file"]) for dataset in plan["datasets"]],
    ]
    backup_entries: List[Dict[str, str]] = []
    try:
        for index, source in enumerate(source_files):
            backup = backup_dir / f"{index:04d}-{source.name}"
            shutil.copy2(source, backup)
            backup_entries.append(
                {"source": str(source), "backup": str(backup)}
            )
    except Exception as error:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise AttachRollbackError(
            f"Could not create attachment backup: {error}"
        ) from error
    plan["backup_dir"] = str(backup_dir)
    plan["backups"] = backup_entries
    context.set_parameter_value(plan_parameter, plan)


def discard_attachment_backup(plan: Dict[str, Any]) -> None:
    backup_dir_value = str(plan.get("backup_dir") or "").strip()
    if backup_dir_value:
        shutil.rmtree(Path(backup_dir_value), ignore_errors=True)
    plan.pop("backup_dir", None)
    plan.pop("backups", None)


def restore_context_snapshot(
    context: CliContextPort,
    plan: Dict[str, Any],
) -> None:
    snapshot = plan.get("context_snapshot")
    if not isinstance(snapshot, dict):
        return
    for parameter_name in _CONTEXT_PARAMETER_NAMES:
        value = snapshot.get(parameter_name)
        if value is None:
            context.delete_parameter(parameter_name)
        else:
            context.set_parameter_value(parameter_name, value)


def restore_attachment(
    context: CliContextPort,
    plan: Dict[str, Any],
    plan_parameter: str,
) -> None:
    backups = plan.get("backups")
    if not isinstance(backups, list) or not backups:
        return
    failures: List[str] = []
    for entry in backups:
        try:
            source = Path(entry["source"])
            backup = Path(entry["backup"])
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, source)
        except Exception as error:
            failures.append(f"{entry}: {error}")
    if failures:
        raise AttachRollbackError("; ".join(failures))
    restore_context_snapshot(context, plan)
    discard_attachment_backup(plan)
    context.set_parameter_value(plan_parameter, plan)


def write_graphs_transactionally(payloads: Dict[Path, Graph]) -> None:
    serialized = {
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
            temporary = path.with_name(f".{path.name}.attach.tmp")
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
