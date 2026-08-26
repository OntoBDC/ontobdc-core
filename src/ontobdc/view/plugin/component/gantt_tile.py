from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ontobdc.context.adapter.dataset_instance import (
    DatasetEntityInstanceRepository,
)
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import (
    ComponentPort,
    TerminalTileRenderable,
)

_VIEW = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
).get_ontology_namespace_by_prefix("obdc_view")

_START_FIELDS: Tuple[str, ...] = (
    "StartTime",
    "ScheduleStart",
    "EarlyStart",
    "ActualStart",
)
_FINISH_FIELDS: Tuple[str, ...] = (
    "FinishTime",
    "ScheduleFinish",
    "EarlyFinish",
    "ActualFinish",
)


class TerminalGanttTile(ComponentPort, TerminalTileRenderable):
    """Terminal Gantt chart for the :view:`GanttTile` standalone tile.

    Reads the matched element's own dataset rows (via
    ``DatasetEntityInstanceRepository``, the same Frictionless
    ``datapackage.json`` resource the element itself belongs to) and draws
    one bar per row, scaled to the earliest start / latest finish across
    every row. Today most schedules only expose the aggregate
    IfcWorkSchedule row itself (a single full-width bar) because their
    IfcTask/IfcTaskTime/IfcRelSequence sheets aren't populated yet — the
    moment those get registered as their own datapackage resource and a
    facade points a standalone tile at that resource instead, this same
    renderer draws every task as its own row without any code change.
    """

    METADATA = ComponentMetadata(
        id="org.ontobdc.view.component.gantt.terminal",
        tag="onto-gantt-tile-terminal",
        tile_class=str(_VIEW.GanttTile),
        version="1.0.0",
        name="Gantt Tile (Terminal)",
        description="Renders a schedule's rows as a text Gantt chart, one bar per row.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "terminal", "gantt", "schedule"],
        min_columns=24,
        min_rows=3,
    )

    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        element: Dict[str, Any] = (context or {}).get("element") or {}
        instances: List[Dict[str, Any]] = self._load_instances(element)
        lines: List[str] = self._render_gantt(instances, width=max(columns, 24))
        return "\n".join(lines)

    def _load_instances(self, element: Dict[str, Any]) -> List[Dict[str, Any]]:
        dataset_path: str = str(element.get("dataset_path") or "").strip()
        entity_reference: str = str(
            element.get("entity_identifier") or element.get("entity_uri") or ""
        ).strip()
        if not dataset_path or not entity_reference:
            return []
        try:
            payload: Dict[str, Any] = DatasetEntityInstanceRepository(
                dataset_path=dataset_path,
                entity=entity_reference,
            ).list_instances()
        except Exception:
            return []
        return list(payload.get("instances") or [])

    def _render_gantt(
        self,
        instances: List[Dict[str, Any]],
        *,
        width: int,
    ) -> List[str]:
        tasks: List[Tuple[str, datetime, datetime]] = []
        for instance in instances:
            name: str = str(
                instance.get("Name") or instance.get("GlobalId") or "Task"
            ).strip()
            start: Optional[datetime] = self._first_date(instance, _START_FIELDS)
            finish: Optional[datetime] = self._first_date(instance, _FINISH_FIELDS)
            if start is None or finish is None:
                continue
            if finish < start:
                start, finish = finish, start
            tasks.append((name, start, finish))

        if not tasks:
            return ["_No task with both a start and finish date was found._"]

        range_start: datetime = min(task[1] for task in tasks)
        range_finish: datetime = max(task[2] for task in tasks)
        span_seconds: float = max(
            1.0, (range_finish - range_start).total_seconds()
        )

        name_width: int = min(28, max(4, max(len(task[0]) for task in tasks)))
        date_width: int = 10  # YYYY-MM-DD
        chrome_width: int = name_width + 2 + date_width + 2 + date_width + 2
        bar_width: int = max(10, width - chrome_width)

        header: str = (
            f"{'TASK':<{name_width}}  {'START':<{date_width}}  "
            f"{'FINISH':<{date_width}}  TIMELINE"
        )
        lines: List[str] = [header, "─" * min(width, len(header) + bar_width)]

        for name, start, finish in tasks:
            offset_ratio: float = (
                start - range_start
            ).total_seconds() / span_seconds
            length_ratio: float = max(
                (finish - start).total_seconds() / span_seconds, 0.02
            )
            offset: int = min(bar_width - 1, int(round(offset_ratio * bar_width)))
            length: int = max(1, int(round(length_ratio * bar_width)))
            length = min(length, bar_width - offset)

            bar: str = (" " * offset) + ("█" * length)
            bar = bar.ljust(bar_width)

            label: str = name[: name_width - 1] + "…" if len(name) > name_width else name
            lines.append(
                f"{label:<{name_width}}  {start.date().isoformat():<{date_width}}  "
                f"{finish.date().isoformat():<{date_width}}  {bar}"
            )

        return lines

    @staticmethod
    def _first_date(
        instance: Dict[str, Any],
        field_names: Tuple[str, ...],
    ) -> Optional[datetime]:
        for field_name in field_names:
            raw_value: Any = instance.get(field_name)
            if not raw_value:
                continue
            text_value: str = str(raw_value).strip()
            if not text_value:
                continue
            try:
                return datetime.fromisoformat(text_value)
            except ValueError:
                continue
        return None
