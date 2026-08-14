from typing import Any

from ontobdc.context.adapter.instance import ContainerEntityInstanceRepository
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort
from ontobdc.shared.facade.port.context import CliContextPort, CliContextStrategyPort


def resolve_entity_by_global_id(
    *, container_path: str, entity: str, global_id: str
) -> dict[str, Any]:
    """Resolve exactly one entity instance without identity fallbacks."""
    payload = ContainerEntityInstanceRepository(
        container_path=container_path, entity=entity
    ).list_instances()
    matches: list[dict[str, Any]] = []
    for instance in payload.get("instances", []):
        if not isinstance(instance, dict):
            continue
        value = instance.get("GlobalId", instance.get("global_id"))
        if str(value or "").strip() == global_id:
            matches.append(dict(instance))
    if not matches:
        raise ValueError(
            f"Could not resolve entity '{entity}' with GlobalId '{global_id}'."
        )
    if len(matches) != 1:
        raise ValueError(
            f"GlobalId '{global_id}' resolves to multiple '{entity}' instances."
        )
    return matches[0]


class EntityGlobalIdStrategy(ParameterPort, CliContextStrategyPort):
    """Resolve an entity instance by its established GlobalId field."""

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.context.parameter.global-id",
        version="0.16.0",
        name="global_id",
        description="Resolve exactly one entity instance by GlobalId.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        global_id = str(context.get_parameter_value("global_id") or "").strip()
        if not global_id:
            raise ValueError("--global-id is required.")
        context.set_parameter_value("global_id", global_id)
        container_path = str(
            context.get_parameter_value("container_path") or ""
        ).strip()
        entity = str(context.get_parameter_value("entity") or "").strip()
        if container_path and entity:
            context.set_parameter_value(
                "entity_instance",
                resolve_entity_by_global_id(
                    container_path=container_path,
                    entity=entity,
                    global_id=global_id,
                ),
            )
        return context
