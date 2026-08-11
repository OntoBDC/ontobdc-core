from pathlib import Path
from typing import Callable

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.view.adapter.surface_context import surface_path_from_context
from ontobdc.view.adapter.surface_document import read_surface, write_surface


class SurfaceTransformationCapability(TransformationCapability):
    """Shared mechanics for cumulative HTML Surface transformations."""

    def _path(self, context: CliContextPort) -> Path:
        return surface_path_from_context(context)

    def _read(self, context: CliContextPort) -> str:
        return read_surface(self._path(context))

    def _write(self, context: CliContextPort, document: str) -> Path:
        path = self._path(context)
        write_surface(path, document)
        context.set_parameter_value("surface_path", str(path))
        return path

    def _check(self, context: CliContextPort, check: Callable[..., int]) -> bool:
        return check(surface_path=str(self._path(context))) == 0

    def _require_check(self, context: CliContextPort, check: Callable[..., int], state_name: str) -> None:
        if not self._check(context, check):
            raise ValueError(f"Surface transformation did not satisfy check for {state_name}")
