from typing import Optional

from rdflib import URIRef

from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.dataset import DatasetRepositoryPort
from ontobdc.shared.domain.port.context import CliContextPort


class DatasetParamResolver:
    def resolve(self, context: CliContextPort, _uri: str, prop: str) -> None:
        dataset_value: Optional[object] = context.get_parameter_value(prop)
        if isinstance(dataset_value, DatasetRepositoryPort):
            return

        if not isinstance(dataset_value, str) or not dataset_value.strip():
            return

        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
        dataset_repository: Optional[DatasetRepositoryPort] = storage_graph.get_dataset(
            dataset_ref=URIRef(dataset_value.strip()),
        )
        if dataset_repository is None:
            return

        context.set_parameter_value(prop, dataset_repository)
