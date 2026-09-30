from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.storage.adapter.repository import StorageContainerRepository
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.port.repository import StorageContainerRepositoryPort


class StorageContainerDataLoaderCapability(DataLoaderCapability):
    """
    Stub capability that exposes a storage container as JSON-compatible data.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.ontobdc.storage.container.plugin.capability.data.loader",
        version="1.0.0",
        name="Storage Container Data Loader",
        description="Load a storage container as JSON-compatible data.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "data-loader", "read-only"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "required": True,
                    "uri": "org.ontobdc.storage.container.id",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                },
                "title": {
                    "type": "string",
                },
                "description": {
                    "type": "string",
                },
                "directory": {
                    "type": "boolean",
                },
            },
            "required": ["id", "title", "description", "directory"],
        },
    )

    def __init__(self, container_id: Optional[str] = None) -> None:
        if container_id is None:
            self._container_id: str = ""
            return

        if not isinstance(container_id, str):
            raise TypeError(
                f"Container id must be a string, got {type(container_id).__name__}."
            )

        self._container_id = container_id.strip()

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, str] = {
            "en": "Storage Container Data Loader",
            "pt-br": "Carregador de Dados do Container de Storage",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, str] = {
            "en": "Loads a storage container as JSON-compatible data.",
            "pt-br": (
                "Carrega um container de storage como dados compatíveis "
                "com JSON."
            ),
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_id: str = self._container_id or str(
            context.get_parameter_value("container_id")
        )

        repository: StorageContainerRepositoryPort = StorageContainerRepository(
            container_id
        )

        return repository.to_json()
