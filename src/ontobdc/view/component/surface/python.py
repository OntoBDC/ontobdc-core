
import shutil
import signal
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from ontobdc.view.domain.port.widget import Widget


@dataclass(frozen=True)
class TerminalSurfaceSize:
    columns: int
    rows: int


@dataclass(frozen=True)
class TerminalSurfaceResizeEvent:
    previous: TerminalSurfaceSize
    current: TerminalSurfaceSize
    logical_columns: int
    visible_logical_rows: int


ResizeListener = Callable[[TerminalSurfaceResizeEvent], None]


class TerminalSurface:
    """Terminal implementation of a PresentationSurface.

    Hosts Widgets and materializes them one below the other, each rendered
    against the current terminal width via `place()`. The terminal size is
    runtime state. A snapshot Surface measures once and renders once. A live
    Surface can observe terminal resize events (SIGWINCH where available) and
    recompute its logical grid.
    """

    def __init__(
        self,
        *,
        dynamic_resize: bool = False,
        slot_width: int = 20,
        slot_height: int = 5,
        horizontal_gap: int = 1,
        vertical_gap: int = 0,
        operation_enabled: bool = True,
        pinned_enabled: bool = True,
        content_mode: str = "scroll",
        fallback_size: Tuple[int, int] = (80, 24),
    ) -> None:
        normalized_mode = str(content_mode).strip().lower()
        if normalized_mode not in {"scroll", "fixed"}:
            raise ValueError("content_mode must be 'scroll' or 'fixed'")
        if slot_width <= 0 or slot_height <= 0:
            raise ValueError("slot dimensions must be positive")
        if horizontal_gap < 0 or vertical_gap < 0:
            raise ValueError("gaps cannot be negative")

        self.dynamic_resize = bool(dynamic_resize)
        self.slot_width = int(slot_width)
        self.slot_height = int(slot_height)
        self.horizontal_gap = int(horizontal_gap)
        self.vertical_gap = int(vertical_gap)
        self.operation_enabled = bool(operation_enabled)
        self.pinned_enabled = bool(pinned_enabled)
        self.content_mode = normalized_mode
        self.fallback_size = fallback_size

        self._size = self.measure()
        self._listeners: List[ResizeListener] = []
        self._previous_sigwinch_handler = None
        self._watching = False

    @property
    def size(self) -> TerminalSurfaceSize:
        return self._size

    @property
    def columns(self) -> int:
        return self._size.columns

    @property
    def rows(self) -> int:
        return self._size.rows

    @property
    def logical_columns(self) -> int:
        pitch = self.slot_width + self.horizontal_gap
        return max(1, (self.columns + self.horizontal_gap) // pitch)

    @property
    def visible_logical_rows(self) -> int:
        reserved_rows = 0
        if self.operation_enabled:
            reserved_rows += self.slot_height
        if self.pinned_enabled:
            reserved_rows += self.slot_height

        content_rows = max(1, self.rows - reserved_rows)
        pitch = self.slot_height + self.vertical_gap
        return max(1, (content_rows + self.vertical_gap) // pitch)

    @property
    def layout_rows(self) -> Optional[int]:
        """Finite logical rows only exist for fixed content.

        Scroll content is vertically unbounded, although visible_logical_rows
        still reports the currently visible runtime capacity.
        """
        if self.content_mode == "scroll":
            return None
        return self.visible_logical_rows

    def place(self, widgets: Sequence[Widget]) -> str:
        """Materialize a sequence of widgets, stacked top to bottom.

        Each widget only sees the current terminal width; the Surface owns
        stacking order and spacing between widgets, not their internal layout.
        """
        blocks: List[str] = [
            "\n".join(rendered_lines)
            for widget in widgets
            if (rendered_lines := widget.render(self.columns))
        ]
        return "\n\n".join(blocks)

    def measure(self) -> TerminalSurfaceSize:
        size = shutil.get_terminal_size(fallback=self.fallback_size)
        return TerminalSurfaceSize(
            columns=max(1, int(size.columns)),
            rows=max(1, int(size.lines)),
        )

    def refresh(self) -> bool:
        """Re-measure and emit SurfaceResized when the runtime size changed."""
        current = self.measure()
        previous = self._size
        if current == previous:
            return False

        self._size = current
        event = TerminalSurfaceResizeEvent(
            previous=previous,
            current=current,
            logical_columns=self.logical_columns,
            visible_logical_rows=self.visible_logical_rows,
        )
        for listener in tuple(self._listeners):
            listener(event)
        return True

    def add_resize_listener(self, listener: ResizeListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_resize_listener(self, listener: ResizeListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def start_resize_watch(self) -> bool:
        """Observe live terminal resize where the platform exposes SIGWINCH.

        Returns True when an OS resize signal was installed. On platforms
        without SIGWINCH, a TUI can call refresh() from its own event loop.
        Snapshot CLI output simply leaves dynamic_resize disabled.
        """
        if not self.dynamic_resize or self._watching:
            return False

        sigwinch = getattr(signal, "SIGWINCH", None)
        if sigwinch is None:
            return False

        self._previous_sigwinch_handler = signal.getsignal(sigwinch)

        def _handle_resize(_signum: int, _frame: object) -> None:
            self.refresh()

        signal.signal(sigwinch, _handle_resize)
        self._watching = True
        return True

    def stop_resize_watch(self) -> None:
        if not self._watching:
            return

        sigwinch = getattr(signal, "SIGWINCH", None)
        if sigwinch is not None and self._previous_sigwinch_handler is not None:
            signal.signal(sigwinch, self._previous_sigwinch_handler)

        self._watching = False
        self._previous_sigwinch_handler = None

    def runtime_state(self) -> dict:
        """Return current PresentationSurface runtime geometry.

        This is intentionally not persisted as generation state: terminal size
        can change after materialization.
        """
        return {
            "width": self.columns,
            "height": self.rows,
            "columns": self.logical_columns,
            "visibleRows": self.visible_logical_rows,
            "layoutRows": self.layout_rows,
            "contentMode": self.content_mode,
            "dynamicResize": self.dynamic_resize,
        }
