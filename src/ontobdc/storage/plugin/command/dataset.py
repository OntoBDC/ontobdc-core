
from pathlib import Path
from typing import List
from rdflib import Graph, URIRef
from urllib.parse import urlparse
from ontobdc.shared.adapter.config import ConfigDataAdapter
from rdflib.namespace import DCTERMS, PROV, RDF
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.storage.domain.port.repository import LoadedStorageGraphPort
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.adapter.dataset import LocalDatasetRepository
from ontobdc.storage import STORAGE_URN_PREFIX, is_enabled, get_storage_file

CT = get_ontology_by_prefix("ct")
DATASET_URN_PREFIX = f"{STORAGE_URN_PREFIX}dataset/"


class StorageDatasetCreateCommand(CliCommandPort):
    """
    Command for dataset creation inside a registered storage container.
    """

    METADATA = CliCommandMetadata(
        id="dataset-create",
        logical_component="storage",
        description="Create a dataset inside a registered storage container.",
        arguments=[
            {
                "accepts": [
                    "--container-id",
                ],
                "valued": True,
                "description": "Target a registered container and create a dataset inside it.",
                "usage": "ontobdc storage --container-id <container_id> --create <dataset_id>",
            },
            {
                "accepts": [
                    "--create",
                ],
                "valued": True,
                "description": "Create a dataset inside the container.",
                "usage": "ontobdc storage --container-id <container_id> --create <dataset_id>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match dataset creation requests for the storage component.
        """
        return (
            len(args) >= 5
            and args[0] == "storage"
            and "--container-id" in args
            and "--create" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        return (
            is_enabled()
            and len(self._request.command_args) >= 4
            and "--container-id" in self._request.command_args
            and "--create" in self._request.command_args
        )

    def run(self) -> CommandResponse:
        try:
            import os
            import subprocess
            import sys
            
            container_idx = self._request.command_args.index("--container-id")
            create_idx = self._request.command_args.index("--create")
            
            container_id = self._request.command_args[container_idx + 1].strip()
            dataset_identifier = self._normalize_dataset_identifier(self._request.command_args[create_idx + 1].strip())

            root_graph: LoadedStorageGraphPort = LoadedStorageGraph(get_storage_file())
            container_subject = self._get_container_subject(root_graph.graph, container_id)
            if not isinstance(container_subject, URIRef):
                raise ValueError(f"Container '{container_id}' is not registered.")

            container_location = self._get_container_location(root_graph.graph, container_subject)
            container_path = self._resolve_location_path(container_location)
            container_storage_file = self._get_container_storage_file(container_path)
            container_graph = self._load_container_graph(container_storage_file)
            dataset_name: str = str(dataset_identifier).split(DATASET_URN_PREFIX)[-1]
            dataset_location = self._build_dataset_location(container_location, dataset_name)
            dataset_path = container_path / dataset_name

            LocalDatasetRepository.create(
                container_graph=container_graph,
                container_subject=container_subject,
                dataset_ref=dataset_identifier,
                dataset_location=dataset_location,
                container_storage_file=container_storage_file
            )

            self._print_info_log(
                f"Created dataset '{dataset_identifier}' in container '{container_id}' at {dataset_location}"
            )

            root_dir: str = ConfigDataAdapter().root_dir

            # Execute hotfix command asynchronously
            try:
                env = os.environ.copy()
                # Inherit the current sys.path to ensure we can import ontobdc dynamically
                env["PYTHONPATH"] = os.pathsep.join(sys.path)

                # Start a detached process that executes the hotfix
                if root_dir:
                    subprocess.Popen(
                        [
                            sys.executable, 
                            "-c", 
                            "import sys; sys.argv=['ontobdc', 'storage', '--fix']; from ontobdc.cli import main; main()"
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=env
                    )
            except Exception as e:
                self._print_info_log(f"Warning: Could not start hotfix process: {e}")

            return CommandResponse(
                title="Storage Dataset Created",
                description=f"Successfully created dataset '{dataset_identifier}' inside container '{container_id}'.",
                content={
                    "container_id": container_id,
                    "dataset_id": str(dataset_identifier),
                    "location": dataset_location,
                    "path": str(dataset_path),
                },
            )
        except Exception as e:
            return CommandResponse(
                title="Failed to Create Dataset",
                description=f"An error occurred while creating the dataset: {str(e)}",
                content={"error": str(e)},
            )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Create Dataset", message)

    def _normalize_dataset_identifier(self, dataset_value: str) -> URIRef:
        normalized = dataset_value.strip()
        if not normalized:
            raise ValueError("Dataset value cannot be empty.")

        parsed = urlparse(normalized)
        if parsed.scheme:
            return URIRef(normalized)

        return URIRef(f"{DATASET_URN_PREFIX}{normalized}")

    def _get_container_subject(self, graph: Graph, container_id: str) -> URIRef | None:
        for subject in graph.subjects(RDF.type, CT.ContainerDescription):
            for obj in graph.objects(subject, DCTERMS.identifier):
                if str(obj) == container_id:
                    return subject
        return None

    def _get_container_location(self, graph: Graph, container_subject: URIRef) -> str:
        location = next(graph.objects(container_subject, PROV.atLocation), None)
        if location is None:
            raise ValueError(f"Container '{container_subject}' has no location.")

        return str(location)

    def _resolve_location_path(self, location_str: str) -> Path:
        if location_str.startswith("file://"):
            return Path(location_str[7:])
        if location_str.startswith("urn:ontobdc:storage/local"):
            root_dir = ConfigDataAdapter().root_dir
            if not root_dir:
                raise ValueError("Project root could not be resolved.")
            resolved = location_str.replace("urn:ontobdc:storage/local", root_dir, 1)
            return Path(resolved)
        return Path(location_str)

    def _build_dataset_location(self, container_location: str, dataset_id: str) -> str:
        base_location = container_location.rstrip("/\\")
        return f"{base_location}/{dataset_id}"

    def _get_container_storage_file(self, container_path: Path) -> Path:
        return container_path / ".__ontobdc__" / "storage.ttl"

    def _load_container_graph(self, container_storage_file: Path) -> Graph:
        if not container_storage_file.is_file():
            raise ValueError(f"Container storage file not found: {container_storage_file}")

        container_graph = Graph()
        container_graph.parse(container_storage_file, format="turtle")
        return container_graph


class StorageDatasetDeleteCommand(CliCommandPort):
    """
    Command for dataset deletion inside a registered storage container.
    """

    METADATA = CliCommandMetadata(
        id="dataset-delete",
        logical_component="storage",
        description="Delete a dataset inside a registered storage container.",
        arguments=[
            {
                "accepts": [
                    "--container-id",
                ],
                "valued": True,
                "description": "Target a registered container and delete a dataset inside it.",
                "usage": "ontobdc storage --container-id <container_id> --delete <dataset_id>",
            },
            {
                "accepts": [
                    "--delete",
                ],
                "valued": True,
                "description": "Delete a dataset inside the container.",
                "usage": "ontobdc storage --container-id <container_id> --delete <dataset_id>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match dataset deletion requests for the storage component.
        """
        return (
            len(args) >= 2
            and args[0] == "storage"
            and "--delete" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        args = self._request.command_args
        if not is_enabled() or "--delete" not in args:
            return False
            
        if "--container-id" not in args and not self._request.context.has_parameter("container_id"):
            # Try to resolve implicitly from context
            from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy
            from ontobdc.storage.plugin.parameter.dataset import DatasetIdStrategy
            DatasetIdStrategy().execute(self._request.context)
            ContainerIdStrategy().execute(self._request.context)
            
            if not self._request.context.has_parameter("container_id"):
                return False
                
        return True

    def run(self) -> CommandResponse:
        try:
            import os
            import subprocess
            import sys
            
            args = self._request.command_args
            
            container_id = None
            if "--container-id" in args:
                container_idx = args.index("--container-id")
                if container_idx + 1 < len(args):
                    container_id = args[container_idx + 1].strip()
            
            if not container_id:
                container_repo = self._request.context.get_parameter_value("container_id")
                if container_repo:
                    container_id = container_repo.id
                    
            if not container_id:
                raise ValueError("Container ID is required")
                
            delete_idx = args.index("--delete")
            if delete_idx + 1 >= len(args) or args[delete_idx + 1].startswith("--"):
                dataset_repo = self._request.context.get_parameter_value("dataset_id")
                if dataset_repo:
                    dataset_value = dataset_repo.id
                else:
                    raise ValueError("Dataset ID is missing after --delete")
            else:
                dataset_value = args[delete_idx + 1].strip()
                
            dataset_identifier = self._normalize_dataset_identifier(dataset_value)

            root_graph: LoadedStorageGraphPort = LoadedStorageGraph(get_storage_file())
            container_subject = self._get_container_subject(root_graph.graph, container_id)
            if not isinstance(container_subject, URIRef):
                raise ValueError(f"Container '{container_id}' is not registered.")

            container_location = self._get_container_location(root_graph.graph, container_subject)
            container_path = self._resolve_location_path(container_location)
            container_storage_file = self._get_container_storage_file(container_path)
            container_graph = self._load_container_graph(container_storage_file)
            dataset_location = self._get_dataset_location(container_graph, dataset_identifier, container_subject)
            dataset_path = self._resolve_location_path(dataset_location)

            if not dataset_path.exists():
                raise ValueError(f"Dataset path not found: {dataset_path}")

            if not dataset_path.is_dir():
                raise ValueError(f"Dataset path is not a directory: {dataset_path}")

            # original_graph_content = container_storage_file.read_text(encoding="utf-8")
            self._remove_dataset_triples(container_graph, dataset_identifier, container_subject)
            container_graph.serialize(destination=str(container_storage_file), format="turtle")

            self._print_info_log(
                f"Deleted dataset '{dataset_identifier}' in container '{container_id}' at {dataset_location}"
            )

            root_dir: str = ConfigDataAdapter().root_dir

            # Execute hotfix command asynchronously
            try:
                env = os.environ.copy()
                # Inherit the current sys.path to ensure we can import ontobdc dynamically
                env["PYTHONPATH"] = os.pathsep.join(sys.path)

                # Start a detached process that executes the hotfix
                if root_dir:
                    subprocess.Popen(
                        [
                            sys.executable, 
                            "-c", 
                            "import sys; sys.argv=['ontobdc', 'storage', '--fix']; from ontobdc.cli import main; main()"
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=env
                    )
            except Exception as e:
                self._print_info_log(f"Warning: Could not start hotfix process: {e}")

            return CommandResponse(
                title="Storage Dataset Deleted",
                description=f"Successfully deleted dataset '{dataset_identifier}' inside container '{container_id}'.",
                content={
                    "container_id": container_id,
                    "dataset_id": str(dataset_identifier),
                    "location": dataset_location,
                    "path": str(dataset_path),
                },
            )
        except Exception as e:
            return CommandResponse(
                title="Failed to Delete Dataset",
                description=f"An error occurred while deleting the dataset: {str(e)}",
                content={"error": str(e)},
            )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Delete Dataset", message)

    def _normalize_dataset_identifier(self, dataset_value: str) -> URIRef:
        normalized = dataset_value.strip()
        if not normalized:
            raise ValueError("Dataset value cannot be empty.")

        parsed = urlparse(normalized)
        if parsed.scheme:
            return URIRef(normalized)

        return URIRef(f"{DATASET_URN_PREFIX}{normalized}")

    def _get_container_subject(self, graph: Graph, container_id: str) -> URIRef | None:
        for subject in graph.subjects(RDF.type, CT.ContainerDescription):
            for obj in graph.objects(subject, DCTERMS.identifier):
                if str(obj) == container_id:
                    return subject
        return None

    def _get_container_location(self, graph: Graph, container_subject: URIRef) -> str:
        location = next(graph.objects(container_subject, PROV.atLocation), None)
        if location is None:
            raise ValueError(f"Container '{container_subject}' has no location.")

        return str(location)

    def _resolve_location_path(self, location_str: str) -> Path:
        if location_str.startswith("file://"):
            return Path(location_str[7:])
        if location_str.startswith("urn:ontobdc:storage/local"):
            root_dir = ConfigDataAdapter().root_dir
            if not root_dir:
                raise ValueError("Project root could not be resolved.")
            resolved = location_str.replace("urn:ontobdc:storage/local", root_dir, 1)
            return Path(resolved)
        return Path(location_str)

    def _get_container_storage_file(self, container_path: Path) -> Path:
        return container_path / ".__ontobdc__" / "storage.ttl"

    def _load_container_graph(self, container_storage_file: Path) -> Graph:
        if not container_storage_file.is_file():
            raise ValueError(f"Container storage file not found: {container_storage_file}")

        container_graph = Graph()
        container_graph.parse(container_storage_file, format="turtle")
        return container_graph

    def _get_dataset_location(
        self,
        graph: Graph,
        dataset_ref: URIRef,
        container_subject: URIRef,
    ) -> str:
        if not any(graph.triples((dataset_ref, DCTERMS.isPartOf, container_subject))):
            raise ValueError(f"Dataset '{dataset_ref}' is not registered in container '{container_subject}'.")

        dataset_location = next(graph.objects(dataset_ref, PROV.atLocation), None)
        if not isinstance(dataset_location, URIRef):
            raise ValueError(f"Dataset '{dataset_ref}' has no location.")

        return str(dataset_location)

    def _remove_dataset_triples(
        self,
        graph: Graph,
        dataset_ref: URIRef,
        container_subject: URIRef,
    ) -> None:
        graph.remove((container_subject, DCTERMS.hasPart, dataset_ref))
        graph.remove((dataset_ref, DCTERMS.isPartOf, container_subject))
        graph.remove((dataset_ref, None, None))
        graph.remove((None, None, dataset_ref))


class StorageDatasetResourceCommand(CliCommandPort):
    """
    Placeholder command for dataset resource actions inside a registered storage container.
    """

    METADATA = CliCommandMetadata(
        id="dataset-resource",
        logical_component="storage",
        description="Placeholder command for dataset resources inside a registered storage container.",
        arguments=[
            {
                "accepts": [
                    "--container-id",
                ],
                "valued": True,
                "description": "Target a registered container.",
                "usage": "ontobdc storage --container-id <container_id> --dataset-id <dataset_id> --resource",
            },
            {
                "accepts": [
                    "--dataset-id",
                ],
                "valued": True,
                "description": "Target a dataset inside the container.",
                "usage": "ontobdc storage --container-id <container_id> --dataset-id <dataset_id> --resource",
            },
            {
                "accepts": [
                    "--resource",
                ],
                "description": "Placeholder dataset resource command.",
                "usage": "ontobdc storage --container-id <container_id> --dataset-id <dataset_id> --resource",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match dataset resource requests for the storage component.
        """
        return (
            len(args) >= 5
            and args[0] == "storage"
            and "--container-id" in args
            and "--dataset-id" in args
            and "--resource" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        return (
            is_enabled()
            and len(self._request.command_args) == 5
            and self._request.command_args[0] == "--container-id"
            and self._request.command_args[2] == "--dataset-id"
            and self._request.command_args[4] == "--resource"
        )

    def run(self) -> CommandResponse:
        container_id = self._request.command_args[1].strip()
        dataset_id = self._request.command_args[3].strip()
        message = f"TODO resource command for dataset '{dataset_id}' in container '{container_id}'."
        self._print_info_log(message)

        return CommandResponse(
            title="Storage Dataset Resource",
            description=message,
            content={
                "container_id": container_id,
                "dataset_id": dataset_id,
                "message": message,
            },
        )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Dataset Resource", message)
