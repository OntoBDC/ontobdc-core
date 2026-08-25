
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.context.adapter.entity_catalog import (
    BrasidataEntityCatalogRepositoryAdapter,
)
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
)
from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy


FACADE_RELATION_LOCAL_NAME: str = "hasDataEntityFacade"
FACADE_FILE_NAME: str = "facade.ttl"
LINKSET_DIRECTORY_NAME: str = "linkset"


class StorageElementCommand(CliCommandPort):
    """List obdc:DataEntity instances registered in a selected storage container."""

    ACTIONS: ClassVar[Tuple[str, ...]] = ("--element",)
    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="element",
        logical_component="storage",
        description="Target elements in a selected storage container.",
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "description": (
                    "Select a registered container by ID or filesystem path."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": False,
                "description": "Target the selected container's elements.",
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": (
                    "Filter elements by an entity URI or entity_identifier."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "--entity <entity-uri-or-identifier>"
                ),
            },
        ],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._ontology_adapter: Optional[OntologyConfigAdapter] = None
        self._entity_catalog_index: Optional[Dict[str, Dict[str, Any]]] = None
        self._entity_filter: str = ""

    @classmethod
    def accepts(cls, args: List[str]) -> bool:
        action_end: int = 3 + len(cls.ACTIONS)
        base_arguments_valid: bool = (
            len(args) >= action_end
            and args[:2] == ["storage", "--container"]
            and bool(str(args[2]).strip())
            and args[3:action_end] == list(cls.ACTIONS)
        )
        if not base_arguments_valid:
            return False
        if len(args) == action_end:
            return True
        return (
            len(args) == action_end + 2
            and args[action_end] == "--entity"
            and bool(str(args[action_end + 1]).strip())
        )

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        action_end: int = 2 + len(self.ACTIONS)
        base_arguments_valid: bool = (
            len(command_args) >= action_end
            and command_args[:1] == ["--container"]
            and bool(str(command_args[1]).strip())
            and command_args[2:action_end] == list(self.ACTIONS)
        )
        filter_arguments_valid: bool = len(command_args) == action_end or (
            len(command_args) == action_end + 2
            and command_args[action_end] == "--entity"
            and bool(str(command_args[action_end + 1]).strip())
        )
        if not base_arguments_valid or not filter_arguments_valid:
            return False

        container_selector: str = str(command_args[1]).strip()
        self._request.context.set_parameter_value(
            "container",
            container_selector,
        )
        if len(command_args) == action_end + 2:
            self._entity_filter = str(
                command_args[action_end + 1]
            ).strip()
            self._request.context.delete_parameter("entity")
        ContainerIdStrategy().execute(self._request.context)

        container_id: str = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        container_path: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()
        if not container_id or not container_path:
            raise CliCommandArgumentException(
                f"Invalid container selector: {container_selector}"
            )

        return True

    def run(self) -> CommandResponse:
        container_id: str = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        container_path_value: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()

        element_rows: List[Dict[str, Any]] = (
            self._list_data_entity_instances(
                container_path=container_path_value,
            )
        )
        entity_identifier_filter: str = (
            self._snake_case(self._local_name(self._entity_filter))
            if self._entity_filter
            else ""
        )
        visible_element_rows: List[Dict[str, str]] = (
            self._compact_element_rows(
                element_rows,
                entity_identifier_filter=entity_identifier_filter,
            )
        )

        return CommandResponse(
            title="Storage Element",
            description=(
                f"Listed {len(visible_element_rows)} obdc:DataEntity instance(s) "
                f"present in the selected storage container."
            ),
            content={
                "container_id": container_id,
                "container_path": container_path_value,
                "elements": visible_element_rows,
            },
        )

    def _filtered_element_rows(
        self,
        element_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        entity_identifier_filter: str = (
            self._snake_case(self._local_name(self._entity_filter))
            if self._entity_filter
            else ""
        )
        return [
            element_row
            for element_row in element_rows
            if not entity_identifier_filter
            or str(element_row.get("entity_identifier") or "").strip()
            == entity_identifier_filter
        ]

    @staticmethod
    def _compact_element_rows(
        element_rows: List[Dict[str, Any]],
        *,
        entity_identifier_filter: str,
    ) -> List[Dict[str, str]]:
        visible_rows: List[Dict[str, str]] = []
        for element_row in element_rows:
            entity_identifier: str = str(
                element_row.get("entity_identifier") or ""
            ).strip()
            if (
                entity_identifier_filter
                and entity_identifier != entity_identifier_filter
            ):
                continue
            visible_rows.append(
                {
                    "global_id": str(element_row.get("id") or "").strip(),
                    "entity_identifier": entity_identifier,
                    "title": str(element_row.get("title") or "").strip(),
                }
            )
        return visible_rows

    def _get_ontology_namespace(self, prefix: str) -> Namespace:
        if self._ontology_adapter is None:
            self._ontology_adapter = OntologyConfigAdapter(
                config_adapter=UnsetProjectRootConfigDataAdapter(),
            )
        namespace: Optional[Namespace] = (
            self._ontology_adapter.get_ontology_namespace_by_prefix(prefix)
        )
        if namespace is None:
            raise ValueError(
                f"Ontology prefix '{prefix}' is not registered."
            )
        return namespace

    def _get_entity_catalog_index(self) -> Dict[str, Dict[str, Any]]:
        if self._entity_catalog_index is not None:
            return self._entity_catalog_index

        root_path_value: str = str(
            getattr(self._request.context, "root_path", "") or ""
        ).strip()
        payload: Dict[str, Any] = (
            BrasidataEntityCatalogRepositoryAdapter(
                root_path=root_path_value or str(Path.cwd()),
            ).list_entities()
        )
        entities: List[Dict[str, Any]] = list(payload.get("entities") or [])
        index: Dict[str, Dict[str, Any]] = {}
        for record in entities:
            entity_uri: str = str(record.get("entity_uri") or "").strip()
            if not entity_uri:
                continue
            index[entity_uri] = record
            entity_identifier: str = str(
                record.get("entity_identifier") or ""
            ).strip()
            if entity_identifier:
                index.setdefault(entity_identifier, record)
        self._entity_catalog_index = index
        return index

    def _load_turtle_graph(self, file_path: Path) -> Graph:
        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))
        graph: Graph = Graph()
        graph.parse(str(file_path), format="turtle")
        return graph

    def _local_name(self, value: Any) -> str:
        raw_value: str = str(value or "").strip()
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1].strip()
        return raw_value.rstrip("/").rsplit("/", 1)[-1].strip()

    def _snake_case(self, value: str) -> str:
        characters: List[str] = []
        for index, character in enumerate(value):
            if (
                character.isupper()
                and index
                and value[index - 1].islower()
            ):
                characters.append("_")
            characters.append(character.lower())
        return "".join(characters)

    def _resolve_dataset_path(
        self,
        *,
        container_path: Path,
        location: Any,
    ) -> Path:
        raw_location: str = str(location or "").strip()
        if not raw_location:
            raise ValueError("Dataset location cannot be empty.")
        parsed = urlparse(raw_location)
        if parsed.scheme == "file":
            return Path(
                url2pathname(unquote(parsed.path))
            ).expanduser().resolve()
        location_path: Path = Path(raw_location).expanduser()
        if not location_path.is_absolute():
            location_path = container_path / location_path
        return location_path.resolve()

    def _resolve_title_with_language(
        self,
        graph: Graph,
        subject: URIRef,
    ) -> Tuple[str, str]:
        best_default_value: str = ""
        best_default_language: str = ""
        best_en_value: str = ""
        best_pt_value: str = ""

        for obj in graph.objects(subject, DCTERMS.title):
            if not isinstance(obj, Literal):
                candidate_value: str = str(obj).strip()
                if candidate_value and not best_default_value:
                    best_default_value = candidate_value
                continue
            value_text: str = str(obj).strip()
            if not value_text:
                continue
            language_code: str = str(getattr(obj, "language", "") or "").strip()
            language_normalized: str = language_code.lower()
            if language_normalized in {"pt-br", "pt"}:
                if not best_pt_value:
                    best_pt_value = value_text
            elif language_normalized.startswith("en"):
                if not best_en_value:
                    best_en_value = value_text
            if not best_default_value:
                best_default_value = value_text
                best_default_language = language_code
        selected_label: str = best_pt_value or best_en_value or best_default_value
        selected_language: str = (
            "pt-BR"
            if best_pt_value
            else (
                "en"
                if best_en_value
                else (
                    best_default_language
                    if best_default_language
                    else "und"
                )
            )
        )
        return selected_label, selected_language

    def _resolve_facade_record(
        self,
        *,
        dataset_path: Path,
        entity_types: List[URIRef],
        conforms_to_facade_uris: List[str],
    ) -> Optional[Dict[str, Any]]:
        catalog_index: Dict[str, Dict[str, Any]] = (
            self._get_entity_catalog_index()
        )
        for entity_type in entity_types:
            entity_type_str: str = str(entity_type).strip()
            record: Optional[Dict[str, Any]] = catalog_index.get(
                entity_type_str
            )
            if record is not None:
                return {
                    "entity_uri": record.get("entity_uri", entity_type_str),
                    "entity_identifier": str(
                        record.get("entity_identifier")
                        or self._snake_case(self._local_name(entity_type))
                    ),
                    "facade_uri": str(
                        record.get("facade_uri") or ""
                    ),
                    "facade_identifier": str(
                        record.get("facade_identifier") or ""
                    ),
                    "facade_name": str(record.get("facade_name") or ""),
                    "facade_name_i18n": str(record.get("facade_name") or ""),
                    "source_kind": "ontology_catalog",
                    "source_path": str(record.get("source_path") or ""),
                }
            identifier_candidate: str = self._snake_case(
                self._local_name(entity_type)
            )
            record_by_identifier: Optional[Dict[str, Any]] = (
                catalog_index.get(identifier_candidate)
            )
            if record_by_identifier is not None:
                return {
                    "entity_uri": str(
                        record_by_identifier.get("entity_uri")
                        or entity_type_str
                    ),
                    "entity_identifier": str(
                        record_by_identifier.get("entity_identifier")
                        or identifier_candidate
                    ),
                    "facade_uri": str(
                        record_by_identifier.get("facade_uri") or ""
                    ),
                    "facade_identifier": str(
                        record_by_identifier.get("facade_identifier")
                        or ""
                    ),
                    "facade_name": str(
                        record_by_identifier.get("facade_name") or ""
                    ),
                    "facade_name_i18n": str(
                        record_by_identifier.get("facade_name") or ""
                    ),
                    "source_kind": "ontology_catalog",
                    "source_path": str(
                        record_by_identifier.get("source_path") or ""
                    ),
                }

        facade_file: Path = (
            StorageBootstrap.get_ontobdc_directory(dataset_path)
            / LINKSET_DIRECTORY_NAME
            / FACADE_FILE_NAME
        )
        if facade_file.is_file():
            facade_graph: Graph = self._load_turtle_graph(facade_file)
            for facade_uri in conforms_to_facade_uris:
                for (
                    facade_subject,
                    title_value,
                ) in facade_graph.subject_objects(DCTERMS.title):
                    if str(facade_subject).strip() != facade_uri:
                        continue
                    name_value: str = ""
                    for obj in facade_graph.objects(
                        facade_subject, DCTERMS.title
                    ):
                        if isinstance(obj, Literal):
                            language: str = str(
                                getattr(obj, "language", "") or ""
                            ).strip().lower()
                            if language in {"pt-br", "pt"}:
                                name_value = str(obj).strip()
                                break
                            if language.startswith("en") and not name_value:
                                name_value = str(obj).strip()
                    if not name_value:
                        name_value = (
                            str(title_value).strip()
                            if isinstance(title_value, Literal)
                            else str(title_value).strip()
                        )
                    facade_identifier: str = self._local_name(
                        facade_subject
                    )
                    entity_uri_value: str = ""
                    for entity_subject in facade_graph.subjects(
                        None, facade_subject
                    ):
                        if str(entity_subject) == facade_uri:
                            continue
                        predicate: Any
                        for predicate in facade_graph.predicates(
                            entity_subject, facade_subject
                        ):
                            if (
                                self._local_name(predicate)
                                == FACADE_RELATION_LOCAL_NAME
                            ):
                                entity_uri_value = str(entity_subject).strip()
                                break
                        if entity_uri_value:
                            break
                    return {
                        "entity_uri": entity_uri_value,
                        "entity_identifier": (
                            self._snake_case(self._local_name(entity_uri_value))
                            if entity_uri_value
                            else ""
                        ),
                        "facade_uri": facade_uri,
                        "facade_identifier": facade_identifier,
                        "facade_name": name_value,
                        "facade_name_i18n": name_value,
                        "source_kind": "dataset_facade_file",
                        "source_path": str(facade_file),
                    }

            for entity_subject, predicate, facade_subject in facade_graph:
                if (
                    self._local_name(predicate)
                    != FACADE_RELATION_LOCAL_NAME
                ):
                    continue
                facade_label: str = ""
                for obj in facade_graph.objects(
                    facade_subject, DCTERMS.title
                ):
                    if isinstance(obj, Literal):
                        language_code: str = str(
                            getattr(obj, "language", "") or ""
                        ).strip().lower()
                        if language_code in {"pt-br", "pt"}:
                            facade_label = str(obj).strip()
                            break
                        if language_code.startswith("en") and not facade_label:
                            facade_label = str(obj).strip()
                if not facade_label:
                    facade_label = self._local_name(facade_subject)
                return {
                    "entity_uri": str(entity_subject).strip(),
                    "entity_identifier": self._snake_case(
                        self._local_name(entity_subject)
                    ),
                    "facade_uri": str(facade_subject).strip(),
                    "facade_identifier": self._local_name(facade_subject),
                    "facade_name": facade_label,
                    "facade_name_i18n": facade_label,
                    "source_kind": "dataset_facade_file",
                    "source_path": str(facade_file),
                }

        if conforms_to_facade_uris:
            first_facade: str = conforms_to_facade_uris[0]
            fallback_facade_name: str = self._local_name(first_facade)
            fallback_entity_uri: str = ""
            if entity_types:
                fallback_entity_uri = str(entity_types[0]).strip()
            return {
                "entity_uri": fallback_entity_uri,
                "entity_identifier": (
                    self._snake_case(self._local_name(fallback_entity_uri))
                    if fallback_entity_uri
                    else ""
                ),
                "facade_uri": first_facade,
                "facade_identifier": fallback_facade_name,
                "facade_name": fallback_facade_name,
                "facade_name_i18n": fallback_facade_name,
                "source_kind": "conforms_to_fallback",
                "source_path": "",
            }
        if entity_types:
            fallback_entity: str = str(entity_types[0]).strip()
            fallback_name: str = self._local_name(fallback_entity)
            return {
                "entity_uri": fallback_entity,
                "entity_identifier": self._snake_case(fallback_name),
                "facade_uri": "",
                "facade_identifier": "",
                "facade_name": fallback_name,
                "facade_name_i18n": fallback_name,
                "source_kind": "entity_type_fallback",
                "source_path": "",
            }
        return None

    def _collect_element_rows_from_dataset(
        self,
        *,
        dataset_path: Path,
        dataset_id: str,
        dataset_title: str,
        rows: List[Dict[str, Any]],
    ) -> None:
        dataset_storage_file: Path = (
            StorageBootstrap.get_dataset_storage_file_path(dataset_path)
        )
        if not dataset_storage_file.is_file():
            return
        obdc: Namespace = self._get_ontology_namespace("obdc")
        dataset_graph: Graph = self._load_turtle_graph(dataset_storage_file)
        raw_subject: Any
        for raw_subject in dataset_graph.subjects(RDF.type, obdc.DataEntity):
            if not isinstance(raw_subject, URIRef):
                continue
            subject: URIRef = raw_subject
            subject_str: str = str(subject).strip()
            if not subject_str:
                continue
            entity_types: List[URIRef] = [
                type_ref
                for type_ref in dataset_graph.objects(subject, RDF.type)
                if isinstance(type_ref, URIRef)
                and str(type_ref).strip() != str(obdc.DataEntity).strip()
            ]
            conforms_to_uris: List[str] = []
            for conforms_obj in dataset_graph.objects(subject, DCTERMS.conformsTo):
                uri_value: str = str(conforms_obj).strip()
                if uri_value and uri_value not in conforms_to_uris:
                    conforms_to_uris.append(uri_value)
            identifier_value: str = ""
            for id_obj in dataset_graph.objects(subject, DCTERMS.identifier):
                if isinstance(id_obj, Literal):
                    candidate_id: str = str(id_obj).strip()
                    if candidate_id:
                        identifier_value = candidate_id
                        break
            if not identifier_value:
                identifier_value = self._local_name(subject)
            title_value, title_language = self._resolve_title_with_language(
                dataset_graph,
                subject,
            )
            facade_record: Optional[Dict[str, Any]] = self._resolve_facade_record(
                dataset_path=dataset_path,
                entity_types=entity_types,
                conforms_to_facade_uris=conforms_to_uris,
            )
            row: Dict[str, Any] = {
                "id": identifier_value,
                "iri": subject_str,
                "identifier": identifier_value,
                "title": title_value,
                "language": title_language,
                "entity_uri": (
                    facade_record.get("entity_uri")
                    if facade_record is not None
                    else ""
                ),
                "entity_identifier": (
                    facade_record.get("entity_identifier")
                    if facade_record is not None
                    else ""
                ),
                "facade_uri": (
                    facade_record.get("facade_uri")
                    if facade_record is not None
                    else ""
                ),
                "facade_identifier": (
                    facade_record.get("facade_identifier")
                    if facade_record is not None
                    else ""
                ),
                "facade_name": (
                    facade_record.get("facade_name")
                    if facade_record is not None
                    else ""
                ),
                "facade_name_i18n": (
                    facade_record.get("facade_name_i18n")
                    if facade_record is not None
                    else ""
                ),
                "source_dataset_id": dataset_id,
                "source_dataset_title": dataset_title,
                "dataset_path": str(dataset_path),
                "source_path": (
                    facade_record.get("source_path")
                    if facade_record is not None
                    else ""
                ),
                "source_kind": (
                    facade_record.get("source_kind")
                    if facade_record is not None
                    else "data_entity_instance"
                ),
            }
            rows.append(row)

    def _list_data_entity_instances(
        self,
        *,
        container_path: str,
    ) -> List[Dict[str, Any]]:
        resolved_container_path: Path = Path(
            container_path
        ).expanduser().resolve()
        container_metadata_path: Path = (
            StorageBootstrap.get_container_storage_file_path(
                resolved_container_path
            )
        )
        if not container_metadata_path.is_file():
            return []
        obdc: Namespace = self._get_ontology_namespace("obdc")
        container_graph: Graph = self._load_turtle_graph(
            container_metadata_path
        )
        container_subjects: List[URIRef] = [
            subject
            for subject in container_graph.subjects(
                RDF.type,
                obdc.DataContainer,
            )
            if isinstance(subject, URIRef)
        ]
        rows: List[Dict[str, Any]] = []
        if not container_subjects:
            return rows
        container_subject: URIRef = container_subjects[0]
        dataset_subjects: List[URIRef] = [
            dataset
            for dataset in container_graph.objects(
                container_subject,
                obdc.hasEntityDataset,
            )
            if isinstance(dataset, URIRef)
            and (
                dataset,
                RDF.type,
                obdc.EntityDataset,
            ) in container_graph
        ]
        for dataset_subject in dataset_subjects:
            dataset_id_value: str = ""
            for id_obj in container_graph.objects(
                dataset_subject, DCTERMS.identifier
            ):
                if isinstance(id_obj, Literal):
                    candidate_id: str = str(id_obj).strip()
                    if candidate_id:
                        dataset_id_value = candidate_id
                        break
            if not dataset_id_value:
                dataset_id_value = self._local_name(dataset_subject)
            dataset_title_value, _ = self._resolve_title_with_language(
                container_graph,
                dataset_subject,
            )
            locations: List[Any] = list(
                container_graph.objects(dataset_subject, PROV.atLocation)
            )
            if len(locations) != 1:
                continue
            dataset_path: Path = self._resolve_dataset_path(
                container_path=resolved_container_path,
                location=locations[0],
            )
            self._collect_element_rows_from_dataset(
                dataset_path=dataset_path,
                dataset_id=dataset_id_value,
                dataset_title=dataset_title_value,
                rows=rows,
            )
        rows.sort(
            key=lambda row: (
                str(row.get("source_dataset_id") or ""),
                str(row.get("entity_identifier") or ""),
                str(row.get("id") or ""),
                str(row.get("iri") or ""),
            )
        )
        return rows
