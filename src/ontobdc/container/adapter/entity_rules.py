from typing import ClassVar, Tuple

from rdflib.namespace import DCTERMS, RDF, XSD

from ontobdc.container.domain.model.entity_facade import EntityFacadeField


class EntityFieldRules:
    """
    Which fields of an entity a person may change.

    Only a plain text field the facade declares can be: the identifier is
    what the entity is, a field that is the type of the entity or holds an
    IRI, a geometry or a timestamp needs more than text to be right, and one
    with many values has no single text to put in its place.
    """

    FIXED_RESOURCES: ClassVar[Tuple[str, ...]] = (str(RDF.type), str(DCTERMS.identifier))
    EDITABLE_DATATYPES: ClassVar[Tuple[str, ...]] = (str(XSD.string),)

    @classmethod
    def is_editable(cls, field: EntityFacadeField) -> bool:
        return (
            field.datatype in cls.EDITABLE_DATATYPES
            and not field.multivalued
            and field.maps_to_resource not in cls.FIXED_RESOURCES
        )
