
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF
from ontobdc.storage import is_enabled, get_storage_file
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.resource.command import CommandResponse
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.storage.adapter.container import StorageLocalContainerAdapter, StorageRootContainerAdapter, LoadedStorageGraph

CT = get_ontology_by_prefix("ct")


class StorageDeleteCommand(CliCommandPort):
    """
    Command for deleting a storage container.
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

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log : callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return is_enabled() and len(self._request.command_args) == 2 and self._request.command_args[0] == "--delete"

    def run(self) -> CommandResponse:
        """
        Execute the command to delete a container.
        """
        try:
            container_id: str = self._request.command_args[1]
            if not container_id.startswith("urn:"):
                container_id = f"urn:ontobdc:storage/local/{container_id}"

            # Load the storage graph
            graph = LoadedStorageGraph(get_storage_file())
            container = StorageLocalContainerAdapter(graph, container_id, "")
            container.delete()

            self._print_info_log(f"Deleted container '{container_id}' from storage index.")

            return CommandResponse(
                title="Container Deleted",
                description=f"Successfully deleted container '{container_id}' from storage index.",
                content={"container_id": container_id}
            )
        except ValueError as e:
            return CommandResponse(
                title="Failed to Delete Container",
                description=str(e),
                content={"error": str(e)}
            )
        except Exception as e:
            return CommandResponse(
                title="Failed to Delete Container",
                description=f"An error occurred: {str(e)}",
                content={"error": str(e)}
            )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Delete Storage", message)
