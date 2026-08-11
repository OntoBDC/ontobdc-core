from os import terminal_size
from typing import List

from ontobdc.view.component.surface.python import TerminalSurface, TerminalSurfaceSize
from ontobdc.view.domain.port.widget import Widget


class _StubWidget(Widget):
    def __init__(self, lines: List[str]) -> None:
        self._lines = lines
        self.seen_available_columns: int = -1

    def render(self, available_columns: int) -> List[str]:
        self.seen_available_columns = available_columns
        return self._lines


def test_snapshot_surface_exposes_current_runtime_geometry(monkeypatch) -> None:
    monkeypatch.setattr(
        "ontobdc.view.component.surface.python.shutil.get_terminal_size",
        lambda fallback: terminal_size((120, 40)),
    )

    surface = TerminalSurface(
        dynamic_resize=False,
        slot_width=20,
        slot_height=5,
        horizontal_gap=1,
        vertical_gap=0,
        operation_enabled=True,
        pinned_enabled=True,
        content_mode="scroll",
    )

    assert surface.size == TerminalSurfaceSize(columns=120, rows=40)
    assert surface.logical_columns == 5
    assert surface.visible_logical_rows == 6
    assert surface.layout_rows is None
    assert surface.runtime_state() == {
        "width": 120,
        "height": 40,
        "columns": 5,
        "visibleRows": 6,
        "layoutRows": None,
        "contentMode": "scroll",
        "dynamicResize": False,
    }


def test_live_surface_emits_resize_event_and_recalculates_grid(monkeypatch) -> None:
    sizes = iter((terminal_size((80, 24)), terminal_size((100, 30))))
    monkeypatch.setattr(
        "ontobdc.view.component.surface.python.shutil.get_terminal_size",
        lambda fallback: next(sizes),
    )

    surface = TerminalSurface(
        dynamic_resize=True,
        slot_width=20,
        slot_height=5,
        horizontal_gap=0,
        vertical_gap=0,
        operation_enabled=True,
        pinned_enabled=True,
        content_mode="fixed",
    )

    events = []
    surface.add_resize_listener(events.append)

    assert surface.refresh() is True
    assert surface.size == TerminalSurfaceSize(columns=100, rows=30)
    assert surface.logical_columns == 5
    assert surface.visible_logical_rows == 4
    assert surface.layout_rows == 4

    assert len(events) == 1
    assert events[0].previous == TerminalSurfaceSize(columns=80, rows=24)
    assert events[0].current == TerminalSurfaceSize(columns=100, rows=30)
    assert events[0].logical_columns == 5
    assert events[0].visible_logical_rows == 4


def test_place_stacks_widgets_and_grants_each_the_current_width(monkeypatch) -> None:
    monkeypatch.setattr(
        "ontobdc.view.component.surface.python.shutil.get_terminal_size",
        lambda fallback: terminal_size((100, 30)),
    )
    surface = TerminalSurface()
    first = _StubWidget(["a", "b"])
    second = _StubWidget(["c"])

    assert surface.place([first, second]) == "a\nb\n\nc"
    assert first.seen_available_columns == 100
    assert second.seen_available_columns == 100


def test_place_skips_widgets_that_render_no_lines(monkeypatch) -> None:
    monkeypatch.setattr(
        "ontobdc.view.component.surface.python.shutil.get_terminal_size",
        lambda fallback: terminal_size((100, 30)),
    )
    surface = TerminalSurface()

    assert surface.place([_StubWidget([]), _StubWidget(["only"])]) == "only"
