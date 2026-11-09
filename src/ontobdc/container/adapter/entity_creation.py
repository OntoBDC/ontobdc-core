from typing import Any, Dict, List

from ontobdc.container.adapter.value_generator import ValueGenerators
from ontobdc.container.domain.model.entity_facade import EntityFacade


class EntityCreation:
    """
    The row of a new instance of an entity: what the person gave, plus the
    default the facade names for each field they left out.
    """

    IDENTIFIER_FIELD: str = "global_id"

    @classmethod
    def record(cls, facade: EntityFacade, given: Dict[str, Any]) -> Dict[str, Any]:
        """
        The given values, a default (a generator's value, or the value the facade
        declares) for every field of the facade that has one
        and was not given (a given value always prevails). Whether the row
        is complete is for the writing to judge.

        Raises:
            ValueError: the facade does not allow creating instances, or the
                given values name fields it does not declare, or have a
                structure where a text goes.
        """
        if not facade.creatable:
            raise ValueError(f"The instances of <{facade.entity_iri}> cannot be created: its facade does not allow it.")

        undeclared: List[str] = [name for name in given if facade.field(name) is None]
        if undeclared:
            raise ValueError(f"The facade of <{facade.entity_iri}> does not declare the fields {undeclared}.")

        record: Dict[str, Any] = {}
        name: str
        value: Any
        for name, value in given.items():
            if isinstance(value, (dict, list)):
                raise ValueError(f"The field {name} takes a text, not a structure.")
            record[name] = "" if value is None else str(value)

        # A field that belongs to other types is not one this entity has: it takes no value.
        had: List[str] = [declared.identifier for declared in facade.fields_of(record)]
        foreign: List[str] = [name for name, text in record.items() if text.strip() and name not in had]
        if foreign:
            raise ValueError(f"The fields {foreign} do not belong to this type of {facade.name}.")

        for field in facade.fields:
            given_value: str = record.get(field.identifier, "")
            if field.options and given_value.strip() and given_value not in field.options:
                raise ValueError(
                    f"The field {field.identifier} takes one of {field.options}, not {given_value!r}."
                )

        for field in facade.fields:
            if field.default is not None and field.default_value is not None:
                raise ValueError(f"The field {field.identifier} declares a default generator and a default value, not one of them.")

            if record.get(field.identifier, "").strip():
                continue

            if field.default is not None:
                record[field.identifier] = ValueGenerators.generate(field.default)
            elif field.default_value is not None:
                record[field.identifier] = field.default_value

        return record
