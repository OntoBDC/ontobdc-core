from typing import Callable, List, Optional

from rdflib import URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.storage.adapter.identifier import ContainerIdentifier
from ontobdc.storage.adapter.repository import (
    LoadedStorageGraph,
    StorageGraphFileRepository,
)
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)

# UnsetProjectRootConfigDataAdapter (not ConfigDataAdapter) so this module
# can be imported for command *discovery* (CommandLoader.get_all(), e.g. to
# build `ontobdc container --help`/`ontobdc --help`) before any project root
# exists yet. The ontology namespace lookup itself doesn't need a real
# project root; only run()'s actual delete does.
_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(UnsetProjectRootConfigDataAdapter())
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


class ContainerDeleteCommand(CliCommandPort):
    """
    Command for unregistering a storage container from the root storage index.

    The container files are left untouched: only its entry in the root
    storage index is removed.
    """

    METADATA = CliCommandMetadata(
        id="ct_delete",
        logical_component="container",
        description="Delete a storage container from the index.",
        arguments=[
            {
                "accepts": [
                    "--delete",
                ],
                "description": (
                    "Storage identifier of the container to unregister "
                    "from the root storage index. Only the index entry is "
                    "removed; the container files on disk are left "
                    "untouched."
                ),
                "valued": True,
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container deletion command at the CLI routing stage.
        """
        return len(args) > 2 and args[0] == "container" and args[1] == "--delete"

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._print_log: Optional[Callable[[str], None]] = None

    def set_print_log(self, print_log: Callable[[str], None]) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return len(self._request.command_args) == 2 and self._request.command_args[0] == "--delete"

    def run(self) -> CommandResponse:
        """
        Remove the entry of the container from the root storage index.
        """
        try:
            container_id: str = ContainerIdentifier.normalize(self._request.command_args[1])
            storage_graph: LoadedStorageGraph = LoadedStorageGraph(StorageFileLocator.resolve())
            container_subject: Optional[URIRef] = self._resolve_container_subject(storage_graph, container_id)
            if container_subject is None:
                raise ValueError(f"Container '{container_id}' is not registered.")

            self._remove_container_from_root_graph(storage_graph, container_subject)
            self._print_info_log(f"Unregistered container '{container_id}' from storage index.")

            return CommandResponse(
                title="Container Unregistered",
                description=f"Successfully unregistered container '{container_id}' from storage index.",
                content={"container_id": container_id},
            )
        except ValueError as error:
            return ExceptionCommandResponse(
                title="Failed to Unregister Container",
                description=str(error),
                content={"error": str(error)},
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="Failed to Unregister Container",
                description=f"An error occurred: {str(error)}",
                content={"error": str(error)},
            )

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

        repository: StorageGraphFileRepository = StorageGraphFileRepository(StorageFileLocator.resolve())
        repository.save(storage_graph.storage_graph)

    def _print_info_log(self, message: str) -> None:
        if self._print_log is not None:
            self._print_log(message)
