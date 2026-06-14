
from typing import Any, Dict, List, Optional
from ontobdc.context.adapter.loader import RemoteResourceLoader
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.context.adapter.remote import RemoteDatasetCapability
from ontobdc.context.domain.port.remote import LinksetDatapackageResourcePort, RemoteResourceLoaderPort
from ontobdc.storage.domain.port.dataset import RemoteDatasetCapabilityVisitorPort, RemoteDatasetRepositoryPort
from rdflib import URIRef

SCHEMA = get_ontology_by_prefix("schema")


class EntityQueryCapabilityVisitor(RemoteDatasetCapabilityVisitorPort):
    """
    Visitor pattern for RemoteDatasetCapability to handle query capabilities.
    """
    def __init__(self, repo: RemoteDatasetRepositoryPort):
        self._remote_dataset_repo: RemoteDatasetRepositoryPort = repo

    @property
    def remote_dataset_repo(self) -> RemoteDatasetRepositoryPort:
        return self._remote_dataset_repo

    def visit(self, capability: RemoteDatasetCapability) -> RemoteDatasetCapability:
        linkset: LinksetDatapackageResourcePort = self.remote_dataset_repo.linkset_datapackage
        output_schema_keys: List[str] = list(capability.metadata.output_schema.get("properties", {}).keys())

        # Find the exact resource by name from output schema
        resources: List[Dict[str, Any]] = []
        for schema_id in output_schema_keys:
            schema_resource = linkset.get_resource_by_name(schema_id)
            if schema_resource:
                entity: Optional[URIRef] = capability.metadata.output_schema.get("properties").get(schema_id, {}).get("entity")
                if isinstance(entity, URIRef):
                    resources.append({
                        **schema_resource,
                        "entity": entity,
                        "load_strategy": RemoteResourceLoader.make(schema_resource)
                    })

        if not resources:
            raise ValueError(f"No valid schema resource found with name '{output_schema_keys}' in the dataset payload.")

        for resource in resources:
            load_strategy: RemoteResourceLoaderPort = resource["load_strategy"]
            data_list: List[Dict[str, Any]] = list(load_strategy.get_entity_instances(self.remote_dataset_repo, resource["entity"]).values())
            capability.accept_gift(resource["name"], data_list)

        return capability