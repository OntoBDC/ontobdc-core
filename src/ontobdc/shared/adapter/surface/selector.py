from __future__ import annotations

from typing import List, Optional, Tuple

from ontobdc.shared.domain.model.surface import SurfaceCapacity, SurfaceDefinition


class DefaultSurfaceLayoutSelector:
    @classmethod
    def select_default_layout(
        cls, capacity: SurfaceCapacity, candidates: List[SurfaceDefinition]
    ) -> Optional[SurfaceDefinition]:
        matching = [candidate for candidate in candidates if cls._matches(candidate, capacity)]
        if not matching:
            return None
        matching.sort(key=cls._selection_key)
        return matching[0]

    @classmethod
    def _matches(cls, candidate: SurfaceDefinition, capacity: SurfaceCapacity) -> bool:
        if cls._is_contradictory(candidate):
            return False

        columns_ok = (
            (candidate.min_available_columns is None or candidate.min_available_columns <= capacity.columns)
            and (candidate.max_available_columns is None or candidate.max_available_columns >= capacity.columns)
        )
        rows_ok = (
            (candidate.min_available_rows is None or candidate.min_available_rows <= capacity.rows)
            and (candidate.max_available_rows is None or candidate.max_available_rows >= capacity.rows)
        )
        return columns_ok and rows_ok

    @classmethod
    def _is_contradictory(cls, candidate: SurfaceDefinition) -> bool:
        columns_contradictory = (
            candidate.min_available_columns is not None
            and candidate.max_available_columns is not None
            and candidate.min_available_columns > candidate.max_available_columns
        )
        rows_contradictory = (
            candidate.min_available_rows is not None
            and candidate.max_available_rows is not None
            and candidate.min_available_rows > candidate.max_available_rows
        )
        return columns_contradictory or rows_contradictory

    @classmethod
    def _selection_key(cls, candidate: SurfaceDefinition) -> Tuple[int, int, int, str]:
        declared, width = cls._specificity(candidate)
        priority = candidate.layout_priority if candidate.layout_priority is not None else 0
        return (-priority, -declared, width, candidate.iri)

    @classmethod
    def _specificity(cls, candidate: SurfaceDefinition) -> Tuple[int, int]:
        bounds = (
            candidate.min_available_columns,
            candidate.max_available_columns,
            candidate.min_available_rows,
            candidate.max_available_rows,
        )
        declared = sum(1 for bound in bounds if bound is not None)

        width = 0
        if candidate.min_available_columns is not None and candidate.max_available_columns is not None:
            width += candidate.max_available_columns - candidate.min_available_columns
        if candidate.min_available_rows is not None and candidate.max_available_rows is not None:
            width += candidate.max_available_rows - candidate.min_available_rows
        return declared, width
