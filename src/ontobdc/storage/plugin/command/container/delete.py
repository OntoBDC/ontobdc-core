from typing import Callable, List, Optional

from rdflib import URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph, StorageGraphFileRepository

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(ConfigDataAdapter())
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


class StorageDeleteCommand(CliCommandPort):
    """
    Command for deleting a storage container from the root storage index.
    """

    METADATA = CliCommandMetadata(
        id="delete",
        logical_component="storage",
        description="Delete a storage container from the index.",
        arguments=[
            {
                "accepts": [
                    "--delete",
                ],
                "description": "Delete a storage container from the index.",
                "usage": "ontobdc storage --delete <container-id>",
                "valued": True,
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) > 2 and args[0] == "storage" and args[1] == "--delete"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[Callable[[str], None]] = None

    def set_print_log(self, print_log: Callable[[str], None]) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        return len(self._request.command_args) == 2 and self._request.command_args[0] == "--delete"

    def run(self) -> CommandResponse:
        try:
            container_id: str = self._normalize_container_id(self._request.command_args[1])
            storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
            container_subject: Optional[URIRef] = self._resolve_container_subject(storage_graph, container_id)
            if container_subject is None:
                raise ValueError(f"Container '{container_id}' is not registered.")

            self._remove_container_from_root_graph(storage_graph, container_subject)
            self._print_info_log(f"Deleted container '{container_id}' from storage index.")

            return CommandResponse(
                title="Container Deleted",
                description=f"Successfully deleted container '{container_id}' from storage index.",
                content={"container_id": container_id},
            )
        except ValueError as error:
            return CommandResponse(
                title="Failed to Delete Container",
                description=str(error),
                content={"error": str(error)},
            )
        except Exception as error:
            return CommandResponse(
                title="Failed to Delete Container",
                description=f"An error occurred: {str(error)}",
                content={"error": str(error)},
            )

    def _normalize_container_id(self, container_id: str) -> str:
        normalized_id: str = container_id.strip()
        if not normalized_id:
            raise ValueError("Container id cannot be empty.")

        if normalized_id.startswith("urn:"):
            return normalized_id

        return f"urn:ontobdc:storage/local/{normalized_id}"

    def _resolve_container_subject(
        self,
        storage_graph: LoadedStorageGraph,
        container_id: str,
    ) -> Optional[URIRef]:
        for subject in storage_graph.graph.subjects(RDF.type, OBDC.DataContainer):
            identifier_values: List[str] = [
                str(identifier).strip()
                for identifier in storage_graph.graph.objects(subject, DCTERMS.identifier)
                if str(identifier).strip()
            ]
            if container_id in identifier_values:
                return subject

        return None

    def _remove_container_from_root_graph(
        self,
        storage_graph: LoadedStorageGraph,
        container_subject: URIRef,
    ) -> None:
        predicate: URIRef
        obj: object
        for predicate, obj in list(storage_graph.graph.predicate_objects(container_subject)):
            storage_graph.graph.remove((container_subject, predicate, obj))

        subject: URIRef
        for subject, predicate, obj in list(storage_graph.graph.triples((None, None, container_subject))):
            storage_graph.graph.remove((subject, predicate, obj))

        repository: StorageGraphFileRepository = StorageGraphFileRepository(get_storage_file())
        repository.save(storage_graph.storage_graph)

    def _print_info_log(self, message: str) -> None:
        if self._print_log is not None:
            self._print_log(message)
