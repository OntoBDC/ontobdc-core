import json
from pathlib import Path
from typing import Any, Dict, Iterable
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
    FrictionlessFormatRegistry,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)


def is_container_publishable(context: CliContextPort) -> bool:
    """Return whether publication metadata matches source container files.

    The active generated Presentation Surface is an output of publication, not
    a source resource. Therefore it is ignored on both sides of the comparison:
    the current container inventory and the already synchronized descriptor.

    Files whose format isn't frictionless-compatible are excluded from the
    comparison too — `ContainerDataPackageFrictionlessValidCapability`
    (run by `container_healthy`, which always precedes this check) prunes
    them from the descriptor on purpose, so requiring them back would put
    this check permanently at odds with that pruning.
    """
    try:
        container_path = _container_path(context)
        root_path = Path(context.root_path).expanduser().resolve()
        if (
            check_container_metadata_ready(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            != 0
        ):
            return False

        expected_paths = {
            path
            for path in ContainerDataPackageSynchronizer.list_resource_paths(
                container_path
            )
            if FrictionlessFormatRegistry.supports(
                path.rsplit(".", 1)[-1].lower()
            )
        }
        described_paths = set(
            _local_descriptor_paths(
                container_path,
                _load_descriptor(container_path),
            )
        )

        generated_surface_path = _generated_surface_relative_path(
            context=context,
            container_path=container_path,
        )
        if generated_surface_path:
            expected_paths.discard(generated_surface_path)
            described_paths.discard(generated_surface_path)

        return expected_paths == described_paths
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _generated_surface_relative_path(
    *,
    context: CliContextPort,
    container_path: Path,
) -> str:
    """Resolve the active Surface output relative to the source container."""
    raw_surface_path = context.get_parameter_value("surface_path")
    if not raw_surface_path:
        # ``surface_path_from_context`` defaults to ``container/index.html``.
        # Publishability runs before surface_initialized, so the context may not
        # have an explicit surface_path yet even when a previous index.html is
        # already present and described by datapackage.json.
        raw_surface_path = container_path / "index.html"

    try:
        surface_path = Path(str(raw_surface_path)).expanduser().resolve()
        return surface_path.relative_to(container_path).as_posix()
    except (OSError, RuntimeError, TypeError, ValueError):
        return ""


def _container_path(context: CliContextPort) -> Path:
    value = context.get_parameter_value("container_path")
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("The container path was not resolved.")

    container_path = Path(normalized).expanduser().resolve()
    if not container_path.is_dir():
        raise ValueError(
            f"Container path is not an accessible directory: {container_path}"
        )
    return container_path


def _load_descriptor(container_path: Path) -> Dict[str, Any]:
    datapackage_path = (
        container_path / ".__ontobdc__" / "datapackage.json"
    )
    loaded = json.loads(datapackage_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(
            f"Invalid container datapackage: {datapackage_path}"
        )
    if not isinstance(loaded.get("resources", []), list):
        raise ValueError(
            "Container datapackage resources must be a list."
        )
    return loaded


def _local_descriptor_paths(
    container_path: Path,
    descriptor: Dict[str, Any],
) -> Iterable[str]:
    metadata_dir = container_path / ".__ontobdc__"
    for item in descriptor.get("resources", []):
        if not isinstance(item, dict):
            continue

        path_value = item.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            continue

        normalized_path = path_value.strip()
        candidate = Path(normalized_path)
        parsed = urlparse(normalized_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        elif parsed.scheme.lower() == "file":
            resolved = Path(
                url2pathname(unquote(parsed.path))
            ).expanduser().resolve()
        elif parsed.scheme:
            continue
        else:
            resolved = (metadata_dir / candidate).resolve()

        try:
            yield resolved.relative_to(container_path).as_posix()
        except ValueError:
            continue
