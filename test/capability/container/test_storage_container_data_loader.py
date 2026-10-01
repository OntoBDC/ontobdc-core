from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.container.plugin.capability.loader.container import (
    StorageContainerDataLoaderCapability,
)


class TestStorageContainerDataLoaderCapability:
    """
    Unit coverage for loading a selected storage container as data.
    """

    @patch(
        "ontobdc.container.plugin.capability.loader.container."
        "StorageContainerRepository"
    )
    def test_execute_returns_repository_data(
        self,
        repository_class: Mock,
    ) -> None:
        container_id: str = "urn:uuid:3ae5682a-0d95-458c-92b8-54c78f533d9b"
        expected_data: Dict[str, Any] = {
            "id": container_id,
            "title": "Storage Container: paint-it-black",
            "description": "Container description",
            "directory": True,
        }
        context: CliContextPort = Mock(spec=CliContextPort)
        context.get_parameter_value.return_value = container_id
        repository: Mock = repository_class.return_value
        repository.to_json.return_value = expected_data
        capability: StorageContainerDataLoaderCapability = (
            StorageContainerDataLoaderCapability()
        )

        result: Dict[str, Any] = capability.execute(context)

        repository_class.assert_called_once_with(container_id)
        repository.to_json.assert_called_once_with()
        assert result == expected_data

    @patch(
        "ontobdc.container.plugin.capability.loader.container."
        "StorageContainerRepository"
    )
    def test_executor_rejects_missing_container_id(
        self,
        repository_class: Mock,
    ) -> None:
        context: CliContextPort = Mock(spec=CliContextPort)
        context.has_parameter.return_value = False
        capability: StorageContainerDataLoaderCapability = (
            StorageContainerDataLoaderCapability()
        )

        with pytest.raises(ValueError, match="Missing required input: container_id"):
            CapabilityExecutor.execute(capability, context)

        repository_class.assert_not_called()
