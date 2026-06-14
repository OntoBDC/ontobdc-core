from typing import Optional

from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.container import StorageContainerAdapter
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort
from ontobdc.shared.domain.port.context import CliContextPort


class ContainerParamResolver:
    def resolve(self, context: CliContextPort, _uri: str, prop: str) -> None:
        container_value: Optional[object] = context.get_parameter_value(prop)
        if isinstance(container_value, ContainerRepositoryPort):
            return

        if not isinstance(container_value, str) or not container_value.strip():
            return

        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
        container_repository: ContainerRepositoryPort = StorageContainerAdapter(
            storage_graph,
            container_value.strip(),
        )
        context.set_parameter_value(prop, container_repository)
