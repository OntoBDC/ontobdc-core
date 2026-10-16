from ontobdc.container.domain.model.entity_facade import EntityFacadeField


class EntityFieldRules:
    """
    Which fields of an entity a person may change.

    The facade decides: a field is editable when the facade declares it
    ``isEditable true``; one that does not say so is not.
    """

    @classmethod
    def is_editable(cls, field: EntityFacadeField) -> bool:
        return field.editable
