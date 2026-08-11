
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ComponentMetadata(BaseModel):
    """
    Data Transfer Object (DTO) describing a presentation Component.

    A Component renders a custom-element `tag`, and is matched one of two
    ways, depending on the request:

    - Content Tiles (a request with a `data` entity reference): matched by
      `required_uris` — RDF type or property URIs (from the domain ontology,
      e.g. `ns.ttl`) the referenced entity must satisfy, checked as
      `rdf:type` or as a populated predicate.
    - Chrome Tiles (a data-less request, e.g. logo/theme/language): matched
      by `tile_class` — the URI of the Tile subclass (from the presentation
      ontology, `view.ttl`, e.g. `:LogoTile`) this component implements.
      There is no entity to test a data requirement against, so the request
      must name the wanted class directly.

    A component declares one path or the other, not both: `required_uris`
    non-empty for content, `tile_class` set for chrome.

    A component also declares the column/row envelope it is willing to
    render at (`min_columns`/`max_columns`/`min_rows`/`max_rows`, all
    `None` meaning "no bound of its own" beyond the surface's own limits).
    For a component whose legibility depends on how much text it renders
    (e.g. a name that must not be cut off), `size_property` names the RDF
    predicate whose literal length drives a dynamic minimum width, sized in
    characters per column via `chars_per_column`. `SurfaceMatchedCapability`
    is what actually turns this into a request envelope — this model only
    declares the bounds, matching `ComponentPort`'s "pure descriptor"
    contract.

    `default_closed` marks a content Tile that shouldn't render open on a
    fresh surface even when auto-matched — e.g. per-file viewer Tiles,
    which should stay hidden until the user opens that specific file. The
    Tile still exists in the document (so client-side code has something to
    reveal), it just starts in a closed/hidden state; `onto-file-tree-tile`
    opens the matching one via the `show-details-requested` Presentation
    Global Event.
    """
    id: str
    tag: str
    version: str
    name: str
    description: str
    author: List[str]
    required_uris: List[str] = Field(default_factory=list)
    tile_class: Optional[str] = None
    tags: Any = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)
    min_columns: int = 1
    max_columns: Optional[int] = None
    min_rows: int = 1
    max_rows: Optional[int] = None
    size_property: Optional[str] = None
    chars_per_column: Optional[int] = None
    default_closed: bool = False
