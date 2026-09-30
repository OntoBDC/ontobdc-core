from typing import List, Optional

from pydantic import BaseModel, Field


class FacadeField(BaseModel):
    """
    One public field a resource facade declares.

    The facade is the name a user recognises, so this carries both what the
    field is called for a person and the property it maps to in RDF, which is
    what a reader or writer of the graph needs.
    """

    identifier: str
    name: str
    description: str
    datatype: str
    order: int
    maps_to_property: str
    required: bool
    editable: bool


class ResourceFacade(BaseModel):
    """
    The public projection of an infrastructure resource.
    """

    identifier: str
    name: str
    description: str
    fields: List[FacadeField] = Field(default_factory=list)

    def field(self, identifier: str) -> Optional[FacadeField]:
        """
        Return the field with the given identifier, or None when undeclared.
        """
        declared_field: FacadeField
        for declared_field in self.fields:
            if declared_field.identifier == identifier:
                return declared_field

        return None

    def editable_fields(self) -> List[FacadeField]:
        """
        Return the fields a user may write, in the order the facade declares.
        """
        return [
            declared_field
            for declared_field in self.fields
            if declared_field.editable
        ]
