
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class PageMetadata(BaseModel):
    """
    Data Transfer Object (DTO) describing a standalone entity detail Page.

    A Page renders one entity as its own full HTML document (as opposed to
    a Component/Tile, which renders inside the Presentation Surface grid).
    It is matched the same way a content Tile is: `required_uris` — RDF
    type URIs an entity must satisfy (checked as `rdf:type`) for this Page
    to claim it.

    `template` names the Jinja template asset (in `ontobdc_view`'s
    `page/asset/`) this Page renders with. `path_segment` is the URL folder
    a rendered instance is published under: `view/<path_segment>/<identifier>.html`.

    A Page is a pure descriptor — matching and rendering live in
    `ontobdc_view`, not here; this model only declares what an entity must
    satisfy and which template to use, matching `ComponentMetadata`'s
    "pure descriptor" contract.
    """
    id: str
    template: str
    path_segment: str
    version: str
    name: str
    description: str
    author: List[str]
    required_uris: List[str] = Field(default_factory=list)
    tags: Any = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)
