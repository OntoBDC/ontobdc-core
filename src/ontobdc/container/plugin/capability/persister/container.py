from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import PersisterCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.repository import StorageContainerRepository
from ontobdc.storage.domain.port.repository import StorageContainerRepositoryPort


class StorageContainerMetadataPersisterCapability(PersisterCapability):
    """
    Persist metadata for a selected storage container.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.container.plugin.capability."
            "metadata.persister"
        ),
        version="1.0.0",
        name="Storage Container Metadata Persister",
        description="Persist metadata for a selected storage container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "metadata", "persistence"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "required": True,
                    "uri": "org.ontobdc.storage.container.id",
                },
                "metadata": {
                    "type": "object",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                },
                "persisted": {
                    "type": "boolean",
                },
            },
            "required": ["id", "persisted"],
        },
    )

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, str] = {
            "en": "Storage Container Metadata Persister",
            "pt-br": "Persistidor de Metadados do Container de Storage",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, str] = {
            "en": "Persists metadata for a selected storage container.",
            "pt-br": "Persiste metadados para um container de storage selecionado.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Write the given metadata into the selected container.
        """
        container_id: Any = context.get_parameter_value("container_id")
        if not isinstance(container_id, str):
            raise TypeError(
                f"Container id must be a string, got "
                f"{type(container_id).__name__}."
            )

        metadata: Any = context.get_parameter_value("metadata")
        if not isinstance(metadata, dict):
            raise TypeError(
                f"Metadata must be an object, got {type(metadata).__name__}."
            )

        repository: StorageContainerRepositoryPort = StorageContainerRepository(
            container_id
        )
        repository.write(metadata)

        return {
            "id": container_id,
            "persisted": True,
        }
