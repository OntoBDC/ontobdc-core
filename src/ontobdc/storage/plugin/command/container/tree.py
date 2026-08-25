from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse, TreeCommandResponse
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.identifier import normalize_container_id
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.adapter.ro_crate_tree import ContainerRoCrateTreeAdapter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.plugin.check.is_container_id_registered.check import (
    get_registered_container_location,
)


class StorageContainerTreeCommand(CliCommandPort):
    """Show a registered container's contents as a tree: its registered
    datasets (by title) followed by its RO-Crate manifest's file tree.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="container_tree",
        logical_component="storage",
        description=(
            "Visualize a registered container's datasets and RO-Crate "
            "manifest as a tree."
        ),
        arguments=[
            {
                "accepts": ["--container-id", "--container"],
                "valued": True,
                "description": "Select a registered container by ID or filesystem path.",
                "usage": "ontobdc storage --container <id-or-path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == "storage"
            and args[1] in {"--container-id", "--container"}
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._container_id: str = ""
        self._container_path: Optional[Path] = None

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 2
            and command_args[0] in {"--container-id", "--container"}
        ):
            return False

        requested_container_id: str = command_args[1].strip()
        if not requested_container_id:
            return False

        resolved_container: Optional[Tuple[str, Path]] = (
            self._resolve_registered_container(requested_container_id)
        )
        if resolved_container is None:
            raise CliCommandArgumentException(
                f"Container is not registered: {requested_container_id}"
            )

        self._container_id, self._container_path = resolved_container
        return True

    def run(self) -> CommandResponse:
        assert self._container_path is not None
        container_title: str = self._resolve_container_title() or self._container_id
        dataset_nodes: List[Dict[str, Any]] = self._list_dataset_nodes(
            self._container_path
        )
        ro_crate_nodes: List[Dict[str, Any]] = (
            ContainerRoCrateTreeAdapter().build_nodes(self._container_path)
        )

        children: List[Dict[str, Any]] = []
        if dataset_nodes:
            children.append(
                {"name": "Datasets", "kind": "section", "children": dataset_nodes}
            )
        children.extend(ro_crate_nodes)

        tree: Dict[str, Any] = {
            "name": container_title,
            "kind": "root",
            "children": children,
        }

        return TreeCommandResponse(
            title="Storage Container",
            description=f"Tree view of container {self._container_id}.",
            content={"tree": tree},
        )

    def _resolve_registered_container(
        self,
        requested_container_id: str,
    ) -> Optional[Tuple[str, Path]]:
        candidates: List[str] = [requested_container_id]
        normalized_candidate: str = normalize_container_id(requested_container_id)
        if normalized_candidate not in candidates:
            candidates.append(normalized_candidate)

        root_path: str = str(self._request.context.root_path)
        for candidate in candidates:
            container_path: Optional[Path] = get_registered_container_location(
                container_id=candidate,
                root_path=root_path,
            )
            if container_path is not None:
                return candidate, container_path

        return None

    def _resolve_container_title(self) -> str:
        root_path: str = str(self._request.context.root_path)
        try:
            storage_graph: LoadedStorageGraph = LoadedStorageGraph(
                get_storage_file(root_path)
            )
        except Exception:
            return ""

        for container in storage_graph.storage_graph.list_containers():
            if not isinstance(container, dict):
                continue
            if str(container.get("id") or "").strip() != self._container_id:
                continue
            return str(container.get("title") or "").strip()

        return ""

    def _list_dataset_nodes(self, container_path: Path) -> List[Dict[str, Any]]:
        container_metadata_path: Path = (
            StorageBootstrap.get_container_storage_file_path(container_path)
        )
        if not container_metadata_path.is_file():
            return []

        obdc: Namespace = self._get_ontology_namespace("obdc")
        graph: Graph = Graph()
        graph.parse(str(container_metadata_path), format="turtle")

        container_subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, obdc.DataContainer)
            if isinstance(subject, URIRef)
        ]
        if not container_subjects:
            return []
        container_subject: URIRef = container_subjects[0]

        dataset_subjects: List[URIRef] = [
            dataset
            for dataset in graph.objects(container_subject, obdc.hasEntityDataset)
            if isinstance(dataset, URIRef)
            and (dataset, RDF.type, obdc.EntityDataset) in graph
        ]

        nodes: List[Dict[str, Any]] = []
        for dataset_subject in dataset_subjects:
            title_value: str = ""
            for title_object in graph.objects(dataset_subject, DCTERMS.title):
                if isinstance(title_object, Literal) and str(title_object).strip():
                    title_value = str(title_object).strip()
                    break
            if not title_value:
                title_value = self._local_name(dataset_subject)

            children: List[Dict[str, Any]] = []
            locations: List[Any] = list(
                graph.objects(dataset_subject, PROV.atLocation)
            )
            if len(locations) == 1:
                dataset_path: Optional[Path]
                try:
                    dataset_path = self._resolve_dataset_path(
                        container_path=container_path,
                        location=locations[0],
                    )
                except Exception:
                    dataset_path = None
                if dataset_path is not None:
                    payload_node: Optional[Dict[str, Any]] = self._build_payload_node(
                        dataset_path
                    )
                    if payload_node is not None:
                        children.append(payload_node)

            nodes.append(
                {"name": title_value, "kind": "dataset", "children": children}
            )

        nodes.sort(key=lambda node: str(node["name"]).lower())
        return nodes

    def _resolve_dataset_path(self, *, container_path: Path, location: Any) -> Path:
        raw_location: str = str(location or "").strip()
        if not raw_location:
            raise ValueError("Dataset location cannot be empty.")
        parsed = urlparse(raw_location)
        if parsed.scheme == "file":
            return Path(url2pathname(unquote(parsed.path))).expanduser().resolve()
        location_path: Path = Path(raw_location).expanduser()
        if not location_path.is_absolute():
            location_path = container_path / location_path
        return location_path.resolve()

    def _build_payload_node(self, dataset_path: Path) -> Optional[Dict[str, Any]]:
        """Read-only filesystem walk of a dataset's ``payload/`` directory.

        Wrapped so a missing/unreadable payload directory never breaks the
        surrounding tree — it just means that dataset shows no payload
        subtree. ``PAYLOAD`` and its direct children (e.g. ``document``,
        the convention seen on real datasets) are shown upper-cased as
        structural group labels; anything deeper keeps its real filename
        casing.
        """
        try:
            payload_dir: Path = dataset_path / "payload"
            if not payload_dir.is_dir():
                return None
            return {
                "name": "PAYLOAD",
                "kind": "dir",
                "children": self._list_directory_nodes(
                    payload_dir, uppercase_dirs=True
                ),
            }
        except Exception:
            return None

    def _list_directory_nodes(
        self,
        directory: Path,
        *,
        uppercase_dirs: bool,
    ) -> List[Dict[str, Any]]:
        entries: List[Path] = sorted(
            (entry for entry in directory.iterdir() if not entry.name.startswith(".")),
            key=lambda entry: (not entry.is_dir(), entry.name.lower()),
        )
        nodes: List[Dict[str, Any]] = []
        for entry in entries:
            if entry.is_dir():
                display_name: str = entry.name.upper() if uppercase_dirs else entry.name
                nodes.append(
                    {
                        "name": display_name,
                        "kind": "dir",
                        "children": self._list_directory_nodes(
                            entry, uppercase_dirs=False
                        ),
                    }
                )
            else:
                nodes.append({"name": entry.name, "kind": "file", "children": []})
        return nodes

    def _get_ontology_namespace(self, prefix: str) -> Namespace:
        ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
            config_adapter=UnsetProjectRootConfigDataAdapter(),
        )
        namespace: Optional[Namespace] = (
            ontology_adapter.get_ontology_namespace_by_prefix(prefix)
        )
        if namespace is None:
            raise ValueError(f"Ontology prefix '{prefix}' is not registered.")
        return namespace

    @staticmethod
    def _local_name(value: Any) -> str:
        raw_value: str = str(value or "").strip()
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1].strip()
        return raw_value.rstrip("/").rsplit("/", 1)[-1].strip()
