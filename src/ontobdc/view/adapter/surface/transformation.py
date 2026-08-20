import time
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

    _REQUIRE_CHECK_MAX_ATTEMPTS: int = 10
    _REQUIRE_CHECK_INITIAL_SLEEP_S: float = 0.01
    _REQUIRE_CHECK_MAX_SLEEP_S: float = 0.2

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
        # Writing to filter-driver backed filesystems (OneDrive / network
        # shares / DFS) is eventually-consistent: the write above returns
        # success but an immediately-following read-back from a different
        # handle sees stale content for tens to hundreds of milliseconds.
        # Retry with capped exponential backoff, short enough to stay
        # invisible on healthy filesystems and long enough for a single
        # filter-driver sync roundtrip.
        sleep_s: float = self._REQUIRE_CHECK_INITIAL_SLEEP_S
        last_ok: bool = self.check(context, check)
        if last_ok:
            return
        for attempt in range(2, self._REQUIRE_CHECK_MAX_ATTEMPTS + 1):
            time.sleep(sleep_s)
            last_ok = self.check(context, check)
            if last_ok:
                return
            sleep_s = min(sleep_s * 2.0, self._REQUIRE_CHECK_MAX_SLEEP_S)
        if not last_ok:
            raise ValueError(
                f"Surface transformation did not satisfy check for {state_name}"
            )
