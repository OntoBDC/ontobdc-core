from pathlib import Path
from typing import Callable

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.view.adapter.surface.context import SurfaceContextAdapter
from ontobdc.view.adapter.surface.document import read_surface, write_surface


class SurfaceTransformationAdapter:
    """Shared mechanics for cumulative HTML Surface transformations.

    Composed by each `surface_*` capability instead of inherited, so a
    capability's type hierarchy stays limited to the Capability contract it
    actually implements — this adapter is not itself a Capability and has no
    METADATA.
    """

    def __init__(self) -> None:
        self._context_adapter = SurfaceContextAdapter()

    def path(self, context: CliContextPort) -> Path:
        return self._context_adapter.surface_path(context)

    def read(self, context: CliContextPort) -> str:
        return read_surface(self.path(context))

    def write(self, context: CliContextPort, document: str) -> Path:
        path = self.path(context)
        write_surface(path, document)
        context.set_parameter_value("surface_path", str(path))
        return path

    def check(self, context: CliContextPort, check: Callable[..., int]) -> bool:
        return check(surface_path=str(self.path(context))) == 0

    def require_check(
        self,
        context: CliContextPort,
        check: Callable[..., int],
        state_name: str,
    ) -> None:
        if not self.check(context, check):
            raise ValueError(
                f"Surface transformation did not satisfy check for {state_name}"
            )
