from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Alignment = Literal["start", "center", "end"]
RegionRole = Literal["OperationRegion", "ContentRegion", "PinnedRegion", "PresentationRegion"]


class SurfaceDefinitionError(ValueError):
    """A Surface RDF graph is missing, contradictory, or otherwise unusable.

    Raised instead of silently producing a partial/incorrect Surface — see
    the CLAUDE.md intervention brief's "fail loudly" requirement.
    """


class ComponentPlacementDefinition(BaseModel):
    iri: str
    component_iri: str
    component_type_iri: Optional[str] = None
    alignment: Alignment = "start"
    order: int = 0


class RegionDefinition(BaseModel):
    iri: str
    role: RegionRole
    row_start: Optional[int] = None
    column_start: Optional[int] = None
    row_span: Optional[int] = None
    column_span: Optional[int] = None
    scrollable: bool = False
    placements: List[ComponentPlacementDefinition] = Field(default_factory=list)


class SurfaceDefinition(BaseModel):
    iri: str
    columns: Optional[int] = None
    rows: Optional[int] = None
    slot_target: Optional[float] = None
    gap: Optional[float] = None
    padding: Optional[float] = None
    regions: List[RegionDefinition] = Field(default_factory=list)

    is_default_layout: bool = False
    min_available_columns: Optional[int] = None
    max_available_columns: Optional[int] = None
    min_available_rows: Optional[int] = None
    max_available_rows: Optional[int] = None
    layout_priority: Optional[int] = None


class SurfaceCapacity(BaseModel):
    """Logical capacity measured for the actual presentation area — not a
    pixel breakpoint. See claude2.md's capacity-measurement formulas; the
    browser renderer derives this the same way it already derives its
    per-region Tile column count."""

    columns: int
    rows: int
