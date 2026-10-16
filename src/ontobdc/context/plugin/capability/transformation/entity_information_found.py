from typing import Any, ClassVar, Dict, Optional

from brasidatacenter.tool.adapter.entity_info import entity_info
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class EntityInformationFoundCapability(TransformationCapability):
    """Find the facade BrasidataCenter publishes for the requested entity, or list every entity when none is requested."""

    INPUT_KEY: ClassVar[str] = "entity_uri"
    OUTPUT_KEY: ClassVar[str] = "entity_information"
    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.entity_information_found",
        version="1.0.0",
        name="Entity Information Found",
        description="Find the facade published for an entity in BrasidataCenter, or list the entities when none is requested.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "entity", "inspection"],
        input_schema={"properties": {INPUT_KEY: {"type": ["string", "null"], "required": False}}},
        output_schema={"properties": {OUTPUT_KEY: {"type": ["object", "array"]}}},
    )

    def label(self, lang: str = "en") -> str:
        return "Entity Information Found"

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        if not context.has_parameter(self.OUTPUT_KEY):
            return False
        information: Any = context.get_parameter_value(self.OUTPUT_KEY)
        entity_id: Optional[str] = RequiredParameter.optional(context, self.INPUT_KEY)
        if entity_id is None:
            return isinstance(information, list)
        return isinstance(information, dict) and information.get("entity_iri") == entity_id

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        entity_id: Optional[str] = RequiredParameter.optional(context, self.INPUT_KEY)
        if entity_id is None:
            information: Any = entity_info()
        else:
            information = entity_info(entity_id)
            if information is None:
                raise LookupError(f"No ontology publishes a facade of the entity <{entity_id}>.")
        context.set_parameter_value(self.OUTPUT_KEY, information)
        return {self.OUTPUT_KEY: information}
