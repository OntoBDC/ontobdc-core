
from rdflib import Graph
from rdflib.namespace import DCTERMS, PROV, RDF
from ontobdc.storage import is_enabled, get_storage_file
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, ListCommandResponse

CT = get_ontology_by_prefix("ct")


class StorageListCommand(CliCommandPort):
    """
    Command for listing storage resources.
    """
    METADATA = CliCommandMetadata(
        id="list",
        logical_component="storage",
        description="List all containers in the storage.",
        arguments=[
            {
                "accepts": [
                    "--list",
                    "-l",
                ],
                "description": "List all containers in the storage.",
                "usage": "ontobdc storage --list",
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
        return is_enabled()

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        storage_path = get_storage_file()
        containers = []

        try:
            g = Graph()
            g.parse(storage_path)
            container_type = CT.ContainerDescription

            for container in g.subjects(RDF.type, container_type):
                container_data = {
                    "id": None,
                    "title": None,
                    "description": None,
                    "location": None
                }

                for id in g.objects(container, DCTERMS.identifier):
                    container_data["id"] = str(id)

                for title in g.objects(container, DCTERMS.title):
                    container_data["title"] = str(title)

                for description in g.objects(container, CT.description):
                    container_data["description"] = str(description)

                for location in g.objects(container, PROV.atLocation):
                    loc_str = str(location)
                    if loc_str.startswith("file://"):
                        loc_str = loc_str[7:]
                    container_data["location"] = loc_str

                containers.append(container_data)

        except Exception as e:
            return CommandResponse(
                title="Failed to List Containers",
                description=f"An error occurred while reading storage.ttl: {str(e)}",
                content={"containers": [], "error": str(e)}
            )

        return CommandResponse(
            title="Storage Containers",
            description=f"Found {len(containers)} container(s) in the storage.",
            content={"containers": containers}
        )

