from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import CapabilityExecutor, PersisterCapability
from ontobdc.container.plugin.capability.persister.container import (
    StorageContainerMetadataPersisterCapability,
)

_CONTAINER_ID: str = "urn:uuid:3ae5682a-0d95-458c-92b8-54c78f533d9b"


class TestStorageContainerMetadataPersisterCapability:
    """
    Unit coverage for persisting metadata of a selected storage container.

    Persistence itself is not implemented yet, so what the capability owns
    today is its declared contract: the metadata it publishes, the input it
    demands before running, and the failure it raises once reached.
    """

    def _context(self, values: Dict[str, Any]) -> CliContextPort:
        context: CliContextPort = Mock(spec=CliContextPort)
        context.has_parameter.side_effect = lambda name: name in values
        context.get_parameter_value.side_effect = values.get

        return context

    def test_is_a_persister_capability(self) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )

        assert isinstance(capability, PersisterCapability)

    def test_declares_its_identity(self) -> None:
        metadata: Any = StorageContainerMetadataPersisterCapability.METADATA

        assert metadata.id == (
            "org.ontobdc.storage.container.plugin.capability.metadata.persister"
        )
        assert metadata.version == "1.0.0"
        assert metadata.name == "Storage Container Metadata Persister"
        assert "persistence" in metadata.tags
        assert metadata.supported_languages == ["en", "pt-br"]

    def test_demands_a_metadata_object_as_input(self) -> None:
        input_schema: Dict[str, Any] = (
            StorageContainerMetadataPersisterCapability.METADATA.input_schema
        )

        metadata_input: Dict[str, Any] = input_schema["properties"]["metadata"]
        assert metadata_input["type"] == "object"
        assert metadata_input["required"] is True

    def test_declares_the_container_it_writes_to_by_uri(self) -> None:
        input_schema: Dict[str, Any] = (
            StorageContainerMetadataPersisterCapability.METADATA.input_schema
        )

        container_input: Dict[str, Any] = input_schema["properties"]["container_id"]
        assert container_input["type"] == "string"
        assert container_input["required"] is True
        assert container_input["uri"] == "org.ontobdc.storage.container.id"

    def test_promises_an_identified_persistence_outcome(self) -> None:
        output_schema: Dict[str, Any] = (
            StorageContainerMetadataPersisterCapability.METADATA.output_schema
        )

        required_outputs: List[str] = output_schema["required"]
        assert required_outputs == ["id", "persisted"]
        assert output_schema["properties"]["id"]["type"] == "string"
        assert output_schema["properties"]["persisted"]["type"] == "boolean"

    def test_labels_and_describes_itself_in_both_declared_languages(self) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )

        assert capability.label("en") == "Storage Container Metadata Persister"
        assert capability.label("pt-br") == (
            "Persistidor de Metadados do Container de Storage"
        )
        assert capability.description("en") == (
            "Persists metadata for a selected storage container."
        )
        assert capability.description("pt-br") == (
            "Persiste metadados para um container de storage selecionado."
        )

    def test_falls_back_to_english_for_an_undeclared_language(self) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )

        assert capability.label("fr") == capability.label("en")
        assert capability.description("fr") == capability.description("en")

    @patch(
        "ontobdc.container.plugin.capability.persister.container."
        "StorageContainerRepository"
    )
    def test_execute_writes_the_metadata_and_reports_the_container(
        self,
        repository_class: Mock,
    ) -> None:
        metadata: Dict[str, Any] = {"title": "Obra Central"}
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )
        context: CliContextPort = self._context(
            {"container_id": _CONTAINER_ID, "metadata": metadata}
        )

        result: Dict[str, Any] = capability.execute(context)

        repository_class.assert_called_once_with(_CONTAINER_ID)
        repository_class.return_value.write.assert_called_once_with(metadata)
        assert result == {"id": _CONTAINER_ID, "persisted": True}

    @patch(
        "ontobdc.container.plugin.capability.persister.container."
        "StorageContainerRepository"
    )
    def test_execute_rejects_a_metadata_that_is_not_an_object(
        self,
        repository_class: Mock,
    ) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )
        context: CliContextPort = self._context(
            {"container_id": _CONTAINER_ID, "metadata": "title=Obra"}
        )

        with pytest.raises(TypeError, match="Metadata must be an object"):
            capability.execute(context)

        repository_class.assert_not_called()

    def test_executor_rejects_a_missing_container_id(self) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )
        context: CliContextPort = self._context({"metadata": {"title": "Obra"}})

        with pytest.raises(ValueError, match="Missing required input: container_id"):
            CapabilityExecutor.execute(capability, context)

    def test_executor_rejects_a_missing_metadata_input(self) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )
        context: CliContextPort = self._context({"container_id": _CONTAINER_ID})

        with pytest.raises(ValueError, match="Missing required input: metadata"):
            CapabilityExecutor.execute(capability, context)

    def test_executor_rejects_a_metadata_input_that_is_not_an_object(self) -> None:
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )
        context: CliContextPort = self._context(
            {"container_id": _CONTAINER_ID, "metadata": "title=Obra"}
        )

        with pytest.raises(ValueError, match="expected object"):
            CapabilityExecutor.execute(capability, context)
