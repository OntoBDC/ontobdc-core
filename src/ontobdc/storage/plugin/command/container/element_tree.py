import re
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
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.identifier import normalize_container_id
from ontobdc.storage.plugin.check.is_container_id_registered.check import (
    get_registered_container_location,
)


class StorageContainerElementTreeCommand(CliCommandPort):
    """Show one obdc:DataEntity element's own RDF properties as a tree, in
    the same visual style as ``ontobdc storage --container <id>``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="container_element_tree",
        logical_component="storage",
        description="Visualize one storage element's properties as a tree.",
        arguments=[
            {
                "accepts": ["--container-id", "--container"],
                "valued": True,
                "description": "Select a registered container by ID or filesystem path.",
                "usage": "ontobdc storage --container <id-or-path> --element <element_id>",
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": (
                    "Select one element by its identifier (the GLOBAL ID "
                    "shown by the bare --element list) and show its tree."
                ),
                "usage": "ontobdc storage --container <id-or-path> --element <element_id>",
            },
        ],
    )

    @staticmethod
    def _is_element_id(value: str) -> bool:
        """A real element id, never a flag belonging to another command.

        Without this guard, ``storage --container <id> --element --explore``
        (5 tokens, same shape as this command's own
        ``--element <element_id>``) would ambiguously match both this
        command and ``StorageExploreCommand`` — "--explore" would look like
        a plausible non-empty element id otherwise.
        """
        stripped: str = str(value or "").strip()
        return bool(stripped) and not stripped.startswith("--")

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 5
            and args[0] == "storage"
            and args[1] in {"--container-id", "--container"}
            and bool(str(args[2]).strip())
            and args[3] == "--element"
            and StorageContainerElementTreeCommand._is_element_id(args[4])
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._container_id: str = ""
        self._container_path: Optional[Path] = None
        self._element_id: str = ""

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 4
            and command_args[0] in {"--container-id", "--container"}
            and command_args[2] == "--element"
        ):
            return False

        requested_container_id: str = command_args[1].strip()
        requested_element_id: str = command_args[3].strip()
        if not requested_container_id or not self._is_element_id(requested_element_id):
            return False

        resolved_container: Optional[Tuple[str, Path]] = (
            self._resolve_registered_container(requested_container_id)
        )
        if resolved_container is None:
            raise CliCommandArgumentException(
                f"Container is not registered: {requested_container_id}"
            )

        self._container_id, self._container_path = resolved_container
        self._element_id = requested_element_id
        return True

    def run(self) -> CommandResponse:
        assert self._container_path is not None
        match: Optional[Tuple[Graph, URIRef]] = self._find_element(
            self._container_path
        )
        if match is None:
            raise CliCommandArgumentException(
                f"Element is not registered in this container: {self._element_id}"
            )
        graph, subject = match

        title_value: str = ""
        for title_object in graph.objects(subject, DCTERMS.title):
            if isinstance(title_object, Literal) and str(title_object).strip():
                title_value = str(title_object).strip()
                break

        root_name: str = (
            f"{self._element_id} — {title_value}"
            if title_value
            else self._element_id
        )

        children: List[Dict[str, Any]] = []
        for predicate, obj in graph.predicate_objects(subject):
            label: str = self._qname_local(graph, predicate)
            value_text: str = self._object_text(graph, obj)
            children.append(
                {
                    "name": f"{label.upper()}: {value_text}",
                    "kind": "property",
                    "children": [],
                }
            )
        children.sort(key=lambda node: str(node["name"]).lower())

        tree: Dict[str, Any] = {
            "name": root_name,
            "kind": "root",
            "children": children,
        }

        return TreeCommandResponse(
            title="Storage Element",
            description=(
                f"Tree view of element {self._element_id} in container "
                f"{self._container_id}."
            ),
            content={"tree": tree},
        )

    def _find_element(
        self,
        container_path: Path,
    ) -> Optional[Tuple[Graph, URIRef]]:
        container_metadata_path: Path = (
            StorageBootstrap.get_container_storage_file_path(container_path)
        )
        if not container_metadata_path.is_file():
            return None

        obdc: Namespace = self._get_ontology_namespace("obdc")
        container_graph: Graph = Graph()
        container_graph.parse(str(container_metadata_path), format="turtle")

        container_subjects: List[URIRef] = [
            subject
            for subject in container_graph.subjects(RDF.type, obdc.DataContainer)
            if isinstance(subject, URIRef)
        ]
        if not container_subjects:
            return None
        container_subject: URIRef = container_subjects[0]

        dataset_subjects: List[URIRef] = [
            dataset
            for dataset in container_graph.objects(
                container_subject, obdc.hasEntityDataset
            )
            if isinstance(dataset, URIRef)
            and (dataset, RDF.type, obdc.EntityDataset) in container_graph
        ]

        for dataset_subject in dataset_subjects:
            locations: List[Any] = list(
                container_graph.objects(dataset_subject, PROV.atLocation)
            )
            if len(locations) != 1:
                continue
            try:
                dataset_path: Path = self._resolve_dataset_path(
                    container_path=container_path,
                    location=locations[0],
                )
            except Exception:
                continue

            dataset_storage_file: Path = (
                StorageBootstrap.get_dataset_storage_file_path(dataset_path)
            )
            if not dataset_storage_file.is_file():
                continue

            dataset_graph: Graph = Graph()
            try:
                dataset_graph.parse(str(dataset_storage_file), format="turtle")
            except Exception:
                continue

            for subject in dataset_graph.subjects(RDF.type, obdc.DataEntity):
                if not isinstance(subject, URIRef):
                    continue
                identifier_value: str = ""
                for id_object in dataset_graph.objects(subject, DCTERMS.identifier):
                    if isinstance(id_object, Literal) and str(id_object).strip():
                        identifier_value = str(id_object).strip()
                        break
                if not identifier_value:
                    identifier_value = self._local_name(subject)
                if identifier_value == self._element_id:
                    return dataset_graph, subject

        return None

    _AUTO_PREFIX_RE = re.compile(r"^ns\d+$")

    @classmethod
    def _qname_local(cls, graph: Graph, predicate: URIRef) -> str:
        try:
            qname: str = graph.namespace_manager.qname(predicate)
        except Exception:
            return cls._local_name(predicate)
        return qname.split(":", 1)[1] if ":" in qname else qname

    @classmethod
    def _object_text(cls, graph: Graph, obj: Any) -> str:
        if isinstance(obj, Literal):
            return str(obj).strip()
        if isinstance(obj, URIRef):
            return cls._qname_or_local(graph, obj)
        return str(obj)

    @classmethod
    def _qname_or_local(cls, graph: Graph, uri: URIRef) -> str:
        # rdflib assigns meaningless auto prefixes (ns1, ns2, …) to any
        # namespace used in the source Turtle without its own ``@prefix``
        # line — showing that raw prefix ("ns1:IfcWorkSchedule") is more
        # confusing than helpful, so fall back to the bare local name.
        try:
            qname: str = graph.namespace_manager.qname(uri)
        except Exception:
            return cls._local_name(uri)
        prefix: str = qname.split(":", 1)[0] if ":" in qname else ""
        if cls._AUTO_PREFIX_RE.match(prefix):
            return cls._local_name(uri)
        return qname

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
