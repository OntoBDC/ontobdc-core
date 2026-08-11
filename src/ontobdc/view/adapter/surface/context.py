from pathlib import Path
from typing import Any, Dict, List, Mapping

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.view.adapter.surface.document import resolve_surface_path


def surface_path_from_context(context: CliContextPort) -> Path:
    raw_surface_path = context.get_parameter_value("surface_path")
    if raw_surface_path:
        return resolve_surface_path(raw_surface_path)

    raw_container_path = context.get_parameter_value("container_path")
    if raw_container_path:
        return Path(str(raw_container_path)).expanduser().resolve() / "index.html"

    raise ValueError("surface_path or container_path is required")


def surface_config_from_context(context: CliContextPort) -> Dict[str, Any]:
    value = context.get_parameter_value("surface_config")
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("surface_config must be an object")
    return dict(value)


def surface_matches_from_context(context: CliContextPort) -> List[Dict[str, Any]]:
    value = context.get_parameter_value("surface_matches")
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("surface_matches must be a list")
    return [dict(item) if isinstance(item, Mapping) else item for item in value]


def component_scripts_from_context(context: CliContextPort) -> List[str]:
    value = context.get_parameter_value("surface_component_scripts")
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [str(script) for script in value.values() if isinstance(script, str) and script.strip()]
    if isinstance(value, list):
        return [str(script) for script in value if isinstance(script, str) and script.strip()]
    raise ValueError("surface_component_scripts must be a list or object of JavaScript source strings")
