from typing import Dict, List, Optional

from pydantic import BaseModel, Field

RDF_TYPE: str = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


class EntityFacadeField(BaseModel):
    """
    One public field the facade of an entity declares: a column of the entity's
    data source and the property its value is written to in RDF.
    """

    identifier: str
    datatype: str
    order: int
    required: bool
    multivalued: bool
    maps_to_resource: str
    editable: bool = False
    default: Optional[str] = None
    default_value: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    # The identifiers of the entity types the field belongs to; none when it belongs to every entity.
    applies_to: List[str] = Field(default_factory=list)
    # Whether the field holds the global ids of entities of the container: its facade of resources is of entities.
    references_entities: bool = False
    # The IRIs of the same classes.
    applies_to_iris: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


class EntityFacade(BaseModel):
    """
    The public projection of an entity: the fields of one row of its data
    source, in the order the facade declares them.
    """

    identifier: str
    name: str
    entity_iri: str
    creatable: bool = False
    commentable: bool = False
    fields: List[EntityFacadeField] = Field(default_factory=list)

    def field(self, identifier: str) -> Optional[EntityFacadeField]:
        """
        Return the field with the given identifier, or None when undeclared.
        """
        declared_field: EntityFacadeField
        for declared_field in self.fields:
            if declared_field.identifier == identifier:
                return declared_field

        return None

    def field_mapped_to(self, resource_iri: str) -> Optional[EntityFacadeField]:
        """
        Return the field written to the given property, or None when none is.
        """
        declared_field: EntityFacadeField
        for declared_field in self.fields:
            if declared_field.maps_to_resource == resource_iri:
                return declared_field

        return None

    def type_field(self) -> Optional[EntityFacadeField]:
        """
        The field that says which type an entity is: the one written to ``rdf:type``.
        """
        return self.field_mapped_to(RDF_TYPE)

    def has_field(self, declared_field: EntityFacadeField, entity_type: str) -> bool:
        """
        Whether an entity of the type has the field: a field that belongs to
        some types only is had by those, and any other belongs to every entity.
        ``entity_type`` is what the entity says it is: the identifier of the
        type, or the IRI of its class, several of them separated by ``|``.
        """
        if not declared_field.applies_to:
            return True

        kinds: List[str] = [kind.strip() for kind in entity_type.split("|") if kind.strip()]
        return any(kind in declared_field.applies_to or kind in declared_field.applies_to_iris for kind in kinds)

    def fields_of(self, values: Dict[str, str]) -> List[EntityFacadeField]:
        """
        The fields an entity has, given its values by field. An entity that
        says no type has the fields that belong to every entity, and no other.
        """
        type_field: Optional[EntityFacadeField] = self.type_field()
        entity_type: str = values.get(type_field.identifier, "").strip() if type_field is not None else ""
        return [declared_field for declared_field in self.fields if self.has_field(declared_field, entity_type)]

    def column_names(self) -> List[str]:
        return [declared_field.identifier for declared_field in self.fields]
