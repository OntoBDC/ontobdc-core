from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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
    options: List[str] = Field(default_factory=list)
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

    def column_names(self) -> List[str]:
        return [declared_field.identifier for declared_field in self.fields]
