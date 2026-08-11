
from abc import ABC
from ontobdc.shared.domain.model.component import ComponentMetadata


class ComponentPort(ABC):
    """
    Base port for presentation Components discovered by ComponentLoader.

    A Component is a pure descriptor — its METADATA declares the
    custom-element tag it renders and the URIs an entity must satisfy for
    the component to match. Components have no behavior of their own;
    matching logic lives in ComponentLoader, not here.
    """
    METADATA: ComponentMetadata
