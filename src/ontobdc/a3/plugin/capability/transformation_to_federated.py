
from pathlib import Path
from typing import Any, Dict
from ontobdc.a32.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a32.domain.machine.response import TransformationResponse
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.resource.capability import CapabilityMetadata, TransformationCapability
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.storage.adapter.resource import TripleFileResource
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph


class TransformationToFederatedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.federated",
        version="0.1.0",
        name="Data package transformation to Federated",
        description="Copy dispatched.jsonld into the dataset payload/documents area and register it in index.ttl.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "federated", "transformation", "jsonld"],
            "pt": ["dados", "federado", "transformacao", "jsonld"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to federate.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The federated data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.FEDERATED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": "Data package transformation to Federated",
            "pt": "Transformacao de pacote de dados para Federado",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": "Copy dispatched.jsonld into the dataset payload/documents area and register it in index.ttl.",
            "pt": "Copia dispatched.jsonld para payload/documents do dataset e o registra no index.ttl.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")
        package_path = etl_package_path.path
        extraction_hash = package_path.name
        dataset_path = package_path.parent

        dispatched_path = package_path / "dispatched.jsonld"
        
        if not dispatched_path.is_file():
            raise FileNotFoundError(f"dispatched.jsonld not found in {package_path}")

        # Rename for federated format to have hash name
        federated_temp_path = package_path / f"{extraction_hash}.jsonld"
        
        # Load global storage graph to find the dataset repository
        storage_graph = LoadedStorageGraph(get_storage_file())
        dataset = storage_graph.get_dataset(str(dataset_path))
        
        if not dataset:
            raise ValueError(f"Dataset not found in storage graph for path {dataset_path}")

        import shutil
        shutil.copy2(dispatched_path, federated_temp_path)

        try:
            # Create a TripleFileResource wrapper
            resource = TripleFileResource(federated_temp_path)
            
            # Delegate entirely to the Dataset's add_resource logic
            dataset.add_resource(resource)
        finally:
            # Clean up temp file
            if federated_temp_path.exists():
                federated_temp_path.unlink()

        return TransformationResponse(resultingState=A3EtlProcessState.FEDERATED)
