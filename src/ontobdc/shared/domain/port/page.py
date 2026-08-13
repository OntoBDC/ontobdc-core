
from abc import ABC
from ontobdc.shared.domain.model.page import PageMetadata


class PagePort(ABC):
    """
    Base port for standalone entity Pages discovered inside `ontobdc_view`.

    A Page is a pure descriptor — its METADATA declares the entity `rdf:type`
    URIs it renders and the Jinja template asset to use. Pages have no
    behavior of their own; matching and rendering live in `ontobdc_view`
    (`render_entity_view`), not here — mirrors `ComponentPort`.
    """
    METADATA: PageMetadata
