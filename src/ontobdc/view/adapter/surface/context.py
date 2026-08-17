from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError
from ontobdc.view.adapter.surface.document import resolve_surface_path


class SurfaceContextAdapter:
    """Resolve Surface-related values from a CLI context.

    Encapsulates extraction of every Surface-domain parameter the state
    machine may read from ``CliContextPort``: paths, match lists, surface
    config dictionaries, optional layout candidates, and component-script
    overrides. Keeps the raw parameter-reading, type-checking, and
    fallback-to-project-config logic in one class so callers (commands,
    capabilities) do not each reimplement the same resolution chain.
    """

    def surface_path(self, context: CliContextPort) -> Path:
        raw_surface_path = context.get_parameter_value("surface_path")
        if raw_surface_path:
            return resolve_surface_path(raw_surface_path)

        raw_container_path = context.get_parameter_value("container_path")
        if raw_container_path:
            return Path(str(raw_container_path)).expanduser().resolve() / "index.html"

        raise ValueError("surface_path or container_path is required")

    def surface_config(self, context: CliContextPort) -> Dict[str, Any]:
        value = context.get_parameter_value("surface_config")
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("surface_config must be an object")
        return dict(value)

    def surface_matches(self, context: CliContextPort) -> List[Dict[str, Any]]:
        value = context.get_parameter_value("surface_matches")
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("surface_matches must be a list")
        return [
            dict(item) if isinstance(item, Mapping) else item for item in value
        ]

    def surface_layouts_path(self, context: CliContextPort) -> Optional[Path]:
        """Resolve which `DefaultSurfaceLayout`/`PresentationSurface` RDF
        (Turtle) file `SURFACE_OPERATIONAL_MATCHED` should read, if any.

        An explicit `surface_layouts_path` context parameter always wins
        (mirrors how `surface_path` overrides the `container_path`-derived
        default) — mainly for tests/programmatic callers. Otherwise falls
        back to the project's `.__ontobdc__/config.yaml`
        (`view.surfaceLayoutsPath`, relative to the project root), the same
        convention `default_language` already uses for
        `context.obdc.contextLanguage`. Returns `None` when neither is set,
        or when no project root can be resolved at all — the caller treats
        that as "no candidates configured", not an error.
        """
        raw_path = context.get_parameter_value("surface_layouts_path")
        if raw_path:
            return Path(str(raw_path)).expanduser().resolve()

        try:
            config = ConfigDataAdapter()
        except ProjectRootDirectoryNotSetError:
            return None

        all_config: Dict[str, Any] = config.all or {}
        view_config: Any = all_config.get("view")
        raw_relative_path: Any = (
            view_config.get("surfaceLayoutsPath")
            if isinstance(view_config, Mapping)
            else None
        )
        if not raw_relative_path:
            return None

        return (config.root_dir / str(raw_relative_path)).resolve()

    def component_scripts(self, context: CliContextPort) -> List[str]:
        value = context.get_parameter_value("surface_component_scripts")
        if value is None:
            return []
        if isinstance(value, Mapping):
            return [
                str(script)
                for script in value.values()
                if isinstance(script, str) and script.strip()
            ]
        if isinstance(value, list):
            return [
                str(script)
                for script in value
                if isinstance(script, str) and script.strip()
            ]
        raise ValueError(
            "surface_component_scripts must be a list or object of JavaScript source strings"
        )
