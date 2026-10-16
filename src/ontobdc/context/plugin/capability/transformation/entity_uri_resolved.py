from typing import Any, ClassVar, Dict, Optional
from urllib.parse import urlsplit

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class EntityUriResolvedCapability(TransformationCapability):
    INPUT_KEY: ClassVar[str] = "entity_id"
    OUTPUT_KEY: ClassVar[str] = "entity_uri"
    SOURCE_KEY: ClassVar[str] = "entity_uri_source"
    ENTITY_URIS: ClassVar[Dict[str, str]] = {
        "annotation": "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation",
        "anotação": "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation",
        "anotacao": "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation",
        "dataset": "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#EntityDataset",
        "entitydataset": "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#EntityDataset",
        "entity_dataset": "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#EntityDataset",
        "datacontainer": "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#DataContainer",
        "data_container": "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#DataContainer",
    }
    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.entity_uri_resolved",
        version="1.0.0", name="Entity URI Resolved",
        description="Resolve a known entity name to its URI, preserving explicit URIs.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "entity", "inspection"],
        input_schema={"properties": {INPUT_KEY: {"type": ["string", "null"], "required": False}}},
        output_schema={"properties": {OUTPUT_KEY: {"type": ["string", "null"]}}},
    )

    def label(self, lang: str = "en") -> str:
        return self.METADATA.name

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    @classmethod
    def resolve(cls, entity: Optional[str]) -> Optional[str]:
        if entity is None:
            return None  # No selector: the next state lists all entity facades.
        if entity.casefold() in cls.ENTITY_URIS:
            return cls.ENTITY_URIS[entity.casefold()]
        if urlsplit(entity).scheme and not any(char.isspace() for char in entity):
            return entity
        raise LookupError(f"No URI is registered for the entity name <{entity}>.")

    def is_satisfied(self, context: CliContextPort) -> bool:
        entity = RequiredParameter.optional(context, self.INPUT_KEY)
        if context.get_parameter_value(self.SOURCE_KEY) != (entity or ""):
            return False
        try:
            return context.get_parameter_value(self.OUTPUT_KEY) == self.resolve(entity)
        except LookupError:
            return False

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        entity = RequiredParameter.optional(context, self.INPUT_KEY)
        uri = self.resolve(entity)
        context.set_parameter_value(self.OUTPUT_KEY, uri)
        context.set_parameter_value(self.SOURCE_KEY, entity or "")
        return {self.OUTPUT_KEY: uri}
