from typing import Any, ClassVar, Dict, List, Optional

from brasidatacenter.tool.adapter.entity_info import entity_info, type_labels
from brasidatacenter.tool.adapter.entity_mapping import entity_iri


class EntityFieldLimits:
    """
    The entity types a field of entities takes, narrowed by the config of the container.

    A field that points to entities takes, by default, the entities of any type: so does the facade
    that BrasidataCenter publishes. The container narrows it in ``.__ontobdc__/config.yaml``, under
    ``constraint``, by the identifier of the facade and then the identifier of the field, with the names of
    the entities the field takes (the names of ``entity.yaml``, in any language they are given)::

        constraint:
          5w2h:
            what:
              accepts: [goal]

    A facade or a field the config does not name is left as it is. A config that names what does not
    exist (a field the facade does not declare, one that does not point to entities, an entity with no
    name) is wrong and says so: a limit that is ignored in silence is worse than none.
    """

    CONFIG_KEY: ClassVar[str] = "constraint"
    ACCEPTS_KEY: ClassVar[str] = "accepts"
    DATA_ENTITY: ClassVar[str] = "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#DataEntity"

    @classmethod
    def applied(cls, information: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        The facade ``information`` (as ``entity_info`` gives it) with the limits the config declares for it:
        the ``entity_types`` of each limited field, and what those types are called.

        Raises:
            ValueError: the config declares a limit that cannot be applied.
        """
        limits: Any = (config or {}).get(cls.CONFIG_KEY)
        if limits is None:
            return information

        if not isinstance(limits, dict):
            raise ValueError(f'The config declares "{cls.CONFIG_KEY}" as something other than a mapping of facades.')

        facade: str = str(information.get("identifier", ""))
        declared: Any = limits.get(facade)
        if declared is None:
            return information

        if not isinstance(declared, dict):
            raise ValueError(f'The config declares "{cls.CONFIG_KEY}.{facade}" as something other than a mapping of fields.')

        fields: Dict[str, Dict[str, Any]] = {str(field["identifier"]): field for field in information.get("fields", [])}
        name: str
        for name, limit in declared.items():
            where: str = f"{cls.CONFIG_KEY}.{facade}.{name}"
            field: Optional[Dict[str, Any]] = fields.get(str(name))
            if field is None:
                raise ValueError(f'The config limits "{where}", but the facade "{facade}" declares no field "{name}".')

            resource: Optional[Dict[str, Any]] = field.get("resource_facade")
            if not isinstance(resource, dict) or not (resource.get("resource_iri") == cls.DATA_ENTITY or resource.get("entity_types")):
                raise ValueError(f'The config limits "{where}", but that field does not point to entities.')

            types: List[str] = cls._types(where, limit)
            resource["entity_types"] = types
            resource["entity_type_labels"] = type_labels(types)

        return information

    @classmethod
    def _types(cls, where: str, limit: Any) -> List[str]:
        accepts: Any = limit.get(cls.ACCEPTS_KEY) if isinstance(limit, dict) else None
        if not isinstance(accepts, list) or not accepts or any(not isinstance(entity, str) or not entity.strip() for entity in accepts):
            raise ValueError(f'The config declares "{where}" without "{cls.ACCEPTS_KEY}", a list of the names of the entities the field takes.')

        published: set[str] = {str(entity["entity_iri"]) for entity in entity_info() or []}
        types: set[str] = set()
        entity: str
        for entity in accepts:
            iri: Optional[str] = entity_iri(entity.strip())
            if iri is None or iri not in published:
                raise ValueError(f'The config says "{where}" takes "{entity}", which is not the name of an entity.')

            types.add(iri)

        return sorted(types)
