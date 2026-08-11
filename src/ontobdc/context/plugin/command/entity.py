import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.adapter.entity_catalog import (
    BrasidataEntityCatalogRepositoryAdapter,
)
from ontobdc.context.adapter.instance import ContainerEntityInstanceRepository
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookArtifact,
    EntityWorkbookField,
)
from ontobdc.storage.adapter.bootstrap import (
    OBDC,
    get_dataset_storage_file_path,
    get_ontobdc_directory,
)
from ontobdc.storage.adapter.machine import DatasetCreateStateTransitionHandler


class ContextEntityCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="entity",
        logical_component="context",
        description=(
            "Display an entity context, list available Brasidata entities, "
            "list container instances, or create one in the entity workbook."
        ),
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": (
                    "Display the persisted information for a context entity."
                ),
                "usage": "ontobdc context --entity <entity_uri>",
            },
            {
                "accepts": ["--all"],
                "valued": False,
                "description": (
                    "List all entity definitions published by "
                    "Brasidata/brasidatacenter."
                ),
                "usage": "ontobdc context --entity --all",
            },
            {
                "accepts": ["--container-id", "--container"],
                "valued": True,
                "description": (
                    "Select the container. Inferred from the current "
                    "directory when omitted, the same way `ontobdc view` "
                    "resolves its container."
                ),
                "usage": (
                    "ontobdc context --container <container_id> "
                    "--entity <entity>"
                ),
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": (
                    "Create one entity instance in the selected container "
                    "workbook. --container is optional: run it from inside "
                    "the target container and it resolves automatically."
                ),
                "usage": (
                    "ontobdc context --create <instance_name> "
                    "--entity <entity> [--container <container_id>]"
                ),
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        has_container_flag: bool = "--container" in args or "--container-id" in args
        is_entity_all: bool = args == ["context", "--entity", "--all"]
        # A bare 3-arg value is ambiguous: a full URI/CURIE (contains ":")
        # means "look up this specific entity resource", while a plain type
        # name (e.g. "WorkStream") means "list instances of this entity
        # type", with the container inferred from the current directory.
        is_entity_lookup: bool = (
            len(args) == 3
            and args[0] == "context"
            and args[1] == "--entity"
            and args[2] != "--all"
            and ":" in args[2]
        )
        is_bare_entity_reference: bool = (
            len(args) == 3
            and args[0] == "context"
            and args[1] == "--entity"
            and args[2] != "--all"
            and ":" not in args[2]
        )
        is_entity_list: bool = is_bare_entity_reference or (
            len(args) == 5
            and args[0] == "context"
            and has_container_flag
            and "--entity" in args
            and "--create" not in args
        )
        is_entity_create: bool = (
            len(args) in (5, 7)
            and args[0] == "context"
            and "--entity" in args
            and "--create" in args
        )
        return (
            is_entity_all
            or is_entity_lookup
            or is_entity_list
            or is_entity_create
        )

    def check(self) -> bool:
        if self._is_entity_all_request():
            return True

        if self._is_entity_lookup_request():
            entity_uri: str = str(
                self._request.context.get_parameter_value("entity_uri") or ""
            ).strip()
            if entity_uri:
                return True

            command_args: List[str] = list(self._request.command_args)
            if len(command_args) != 2:
                raise CliCommandArgumentException(
                    "Usage: ontobdc context --entity <entity_uri>"
                )

            raw_entity_value: str = str(command_args[1]).strip()
            if not raw_entity_value:
                raise CliCommandArgumentException(
                    "Usage: ontobdc context --entity <entity_uri>"
                )

            self._request.context.set_parameter_value(
                "entity_uri",
                raw_entity_value,
            )
            return True

        # container_id/container_path/entity/create are already bound by cli/__init__.py's _check_command before check() runs.
        container_id: str = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        container_path: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()
        if not container_id or not container_path:
            raise CliCommandArgumentException(
                "Could not resolve a container. Run this command inside a "
                "registered container, or pass --container <container_id>."
            )

        entity_value: str = str(
            self._request.context.get_parameter_value("entity") or ""
        ).strip()
        if not entity_value:
            raise CliCommandArgumentException(
                "Usage: ontobdc context --entity <entity> "
                "[--container <container_id>]"
            )

        if self._is_entity_create_request():
            root_path: str = str(self._request.context.root_path).strip()
            facade: Optional[Dict[str, Any]] = EntityVectorRepositoryAdapter(
                root_path=root_path,
            ).resolve_entity_facade(entity_value)
            if facade is None:
                raise CliCommandArgumentException(
                    f"Could not resolve entity facade: {entity_value}"
                )

            self._request.context.set_parameter_value(
                "entity_uri",
                str(facade["entity_uri"]),
            )
            self._request.context.set_parameter_value(
                "entity_facade",
                facade,
            )
            create_value: str = str(
                self._request.context.get_parameter_value("create") or ""
            ).strip()
            if not create_value:
                raise CliCommandArgumentException(
                    "Usage: ontobdc context --create <instance_name> "
                    "--entity <entity> [--container <container_id>]"
                )

        return True

    def run(self) -> CommandResponse:
        if self._is_entity_all_request():
            return self._run_list_all_entities()

        if self._is_entity_lookup_request():
            entity_uri: str = str(
                self._request.context.get_parameter_value("entity_uri") or ""
            ).strip()
            return CommandResponse(
                title="Context Entity",
                description=(
                    "Display the persisted information for entity "
                    f"'{entity_uri}'."
                ),
                content={
                    "entity_uri": entity_uri,
                },
            )

        if self._is_entity_create_request():
            return self._run_create_instance()

        return self._run_list_instances()

    def _is_entity_all_request(self) -> bool:
        return list(self._request.command_args) == ["--entity", "--all"]

    def _is_entity_lookup_request(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        return (
            len(command_args) == 2
            and command_args[0] == "--entity"
            and command_args[1] != "--all"
            and ":" in command_args[1]
        )

    def _is_entity_create_request(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        return (
            len(command_args) in (4, 6)
            and "--entity" in command_args
            and "--create" in command_args
        )

    def _run_list_all_entities(self) -> CommandResponse:
        root_path: str = str(self._request.context.root_path).strip()
        payload: Dict[str, Any] = (
            BrasidataEntityCatalogRepositoryAdapter(
                root_path=root_path,
            ).list_entities()
        )
        entity_count: int = int(payload.get("entity_count") or 0)
        source_repository: str = str(
            payload.get("source_repository") or "Brasidata/brasidatacenter"
        ).strip()

        return CommandResponse(
            title="Brasidata Entity Catalog",
            description=(
                f"Listed {entity_count} entity definition(s) from "
                f"'{source_repository}'."
            ),
            content=payload,
        )

    def _run_list_instances(self) -> CommandResponse:
        container_id: str = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        container_path: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()
        entity_value: str = str(
            self._request.context.get_parameter_value("entity") or ""
        ).strip()
        repository: ContainerEntityInstanceRepository = (
            ContainerEntityInstanceRepository(
                container_path=container_path,
                entity=entity_value,
            )
        )
        payload: Dict[str, Any] = repository.list_instances()

        return CommandResponse(
            title="Context Entity Instances",
            description=(
                f"Listed {int(payload['instance_count'])} instance(s) of "
                f"entity '{str(payload['entity'])}' in container "
                f"'{container_id}'."
            ),
            content={
                "container_id": container_id,
                "container_path": container_path,
                "entity": str(payload["entity"]),
                "entity_uri": str(payload["entity_uri"]),
                "resolution": str(payload["resolution"]),
                "dataset_count": int(payload["dataset_count"]),
                "datasets": list(payload["datasets"]),
                "instance_count": int(payload["instance_count"]),
                "instances": list(payload["instances"]),
            },
        )

    def _run_create_instance(self) -> CommandResponse:
        facade: Dict[str, Any] = dict(
            self._request.context.get_parameter_value("entity_facade") or {}
        )
        create_value: str = str(
            self._request.context.get_parameter_value("create") or ""
        ).strip()
        container_path: Path = Path(
            str(
                self._request.context.get_parameter_value("container_path")
                or ""
            ).strip()
        ).expanduser().resolve()

        entity_identifier: str = str(
            facade.get("entity_identifier") or ""
        ).strip()
        dataset_path: Path = self._resolve_new_dataset_path(
            container_path=container_path,
            entity_identifier=entity_identifier,
            create_value=create_value,
        )
        self._create_dataset(dataset_path)

        workbook_contract: Dict[str, Any] = self._build_workbook_contract(
            facade=facade,
            dataset_path=dataset_path,
        )
        adapter: EntityWorkbookAdapter = EntityWorkbookAdapter()
        records: List[Dict[str, Any]] = adapter.read(
            workbook_path=Path(
                str(workbook_contract["workbook_path"])
            ).expanduser().resolve(),
            worksheet_name=str(workbook_contract["worksheet_name"]),
            fields=list(workbook_contract["fields"]),
        )

        target_field_name: str = self._resolve_target_field_name(
            facade=facade
        )
        if not target_field_name:
            raise CliCommandArgumentException(
                "Could not resolve a writable entity field."
            )

        instance_identifier: str = str(uuid.uuid4())
        new_record: Dict[str, Any] = {
            field.name: ""
            for field in list(workbook_contract["fields"])
        }
        if "GlobalId" in new_record:
            new_record["GlobalId"] = instance_identifier
        new_record[target_field_name] = create_value
        records.append(new_record)

        artifact: EntityWorkbookArtifact = adapter.generate(
            output_dir=Path(
                str(workbook_contract["output_dir"])
            ).expanduser().resolve(),
            workbook_name=str(workbook_contract["workbook_name"]),
            worksheet_name=str(workbook_contract["worksheet_name"]),
            fields=list(workbook_contract["fields"]),
            records=records,
            datapackage_path=Path(
                str(workbook_contract["datapackage_path"])
            ).expanduser().resolve(),
            package_name="ontobdc_container",
            resource_name=str(workbook_contract["resource_name"]),
            primary_key=list(workbook_contract["primary_key"]),
            entity_uri=str(workbook_contract["entity_uri"]),
            entity_identifier=str(workbook_contract["entity_identifier"]),
            facade_uri=str(workbook_contract["facade_uri"]),
        )

        entity_subject: str = self._relate_entity_in_dataset(
            dataset_path=dataset_path,
            facade=facade,
            entity_identifier=instance_identifier,
            entity_title=create_value,
        )
        self._materialize_dataset_facade(dataset_path=dataset_path, facade=facade)

        return CommandResponse(
            title="Context Entity Created",
            description=(
                "Created one instance of entity "
                f"'{str(facade.get('entity_name') or '').strip()}' "
                f"in dataset '{dataset_path.name}' of container "
                f"'{str(self._request.context.get_parameter_value('container_id') or '').strip()}'."
            ),
            content={
                "container_id": str(
                    self._request.context.get_parameter_value("container_id")
                    or ""
                ).strip(),
                "container_path": str(
                    self._request.context.get_parameter_value("container_path")
                    or ""
                ).strip(),
                "dataset_path": str(dataset_path),
                "entity": str(
                    facade.get("entity_name") or ""
                ).strip(),
                "entity_uri": str(
                    self._request.context.get_parameter_value("entity_uri")
                    or ""
                ).strip(),
                "entity_subject": entity_subject,
                "target_field": target_field_name,
                "created_value": create_value,
                "workbook_path": str(artifact.workbook_path),
                "worksheet_name": artifact.worksheet_name,
                "datapackage_path": str(artifact.datapackage_path),
                "instance_count": artifact.generated_row_count,
                "validation": artifact.validation,
            },
        )

    def _slugify(self, value: str) -> str:
        normalized: str = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
        return normalized or "instance"

    def _resolve_new_dataset_path(
        self,
        *,
        container_path: Path,
        entity_identifier: str,
        create_value: str,
    ) -> Path:
        slug: str = f"{entity_identifier}-{self._slugify(create_value)}"
        candidate: Path = container_path / slug
        suffix: int = 2
        while candidate.exists():
            candidate = container_path / f"{slug}-{suffix}"
            suffix += 1
        return candidate

    def _create_dataset(self, dataset_path: Path) -> None:
        self._request.context.set_parameter_value(
            "dataset_path",
            str(dataset_path),
        )
        handler = DatasetCreateStateTransitionHandler(
            context=self._request.context,
        )
        handler.execute()

    def _relate_entity_in_dataset(
        self,
        *,
        dataset_path: Path,
        facade: Dict[str, Any],
        entity_identifier: str,
        entity_title: str,
    ) -> str:
        """Replace the dataset's generic hasDataEntity stub with a properly-typed, facade-conformant one."""
        dataset_storage_file_path: Path = get_dataset_storage_file_path(
            dataset_path
        )
        graph: Graph = Graph()
        graph.parse(str(dataset_storage_file_path), format="turtle")

        dataset_subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, OBDC.EntityDataset)
            if isinstance(subject, URIRef)
        ]
        if len(dataset_subjects) != 1:
            raise CliCommandArgumentException(
                f"Dataset metadata is invalid: {dataset_storage_file_path}"
            )
        dataset_subject: URIRef = dataset_subjects[0]

        for stale_entity in list(
            graph.objects(dataset_subject, OBDC.hasDataEntity)
        ):
            graph.remove((dataset_subject, OBDC.hasDataEntity, stale_entity))

        entity_subject: URIRef = URIRef(f"{dataset_subject}/{entity_identifier}")
        graph.add((dataset_subject, OBDC.hasDataEntity, entity_subject))
        graph.add((entity_subject, RDF.type, OBDC.DataEntity))

        entity_type_uri: str = str(facade.get("entity_uri") or "").strip()
        if entity_type_uri:
            graph.add((entity_subject, RDF.type, URIRef(entity_type_uri)))
            self._materialize_surfaceable_marker(
                graph=graph,
                entity_type_uri=entity_type_uri,
                facade=facade,
            )

        facade_uri: str = str(facade.get("facade_uri") or "").strip()
        if facade_uri:
            graph.add((entity_subject, DCTERMS.conformsTo, URIRef(facade_uri)))

        graph.add(
            (entity_subject, DCTERMS.identifier, Literal(entity_identifier))
        )
        language: str = str(self._request.context.language or "en").strip()
        graph.add(
            (entity_subject, DCTERMS.title, Literal(entity_title, lang=language))
        )

        graph.serialize(destination=str(dataset_storage_file_path), format="turtle")
        return str(entity_subject)

    def _materialize_surfaceable_marker(
        self,
        *,
        graph: Graph,
        entity_type_uri: str,
        facade: Dict[str, Any],
    ) -> None:
        """Copy the entity type's own obdc:SurfaceableEntity assertion (if
        any) into dataset.ttl, so the Surface can see it without loading an
        external domain ontology file itself.

        The type ontology (e.g. type.ttl) is a sibling of the facade file
        EntityVectorRepositoryAdapter already resolved — reusing that path
        avoids a second, separate ontology-resolution mechanism in the
        storage/view layers, which must not depend on this context layer.
        """
        source_file: str = str(facade.get("source_file") or "").strip()
        if not source_file:
            return

        type_ontology_path: Path = (
            Path(source_file).expanduser().resolve().parent / "type.ttl"
        )
        if not type_ontology_path.is_file():
            return

        type_graph: Graph = Graph()
        try:
            type_graph.parse(str(type_ontology_path), format="turtle")
        except Exception:
            return

        entity_type: URIRef = URIRef(entity_type_uri)
        if (entity_type, RDF.type, OBDC.SurfaceableEntity) in type_graph:
            graph.add((entity_type, RDF.type, OBDC.SurfaceableEntity))

    def _materialize_dataset_facade(
        self,
        *,
        dataset_path: Path,
        facade: Dict[str, Any],
    ) -> None:
        """Copy the resolved facade into the dataset's own linkset/facade.ttl,
        which the list path reads from, and its sibling type.ttl (if any)
        into linkset/type.ttl — a local copy of the entity type's own
        ontology file, so a storage-layer check can later verify (and, on
        `ontobdc storage --update`, hotfix) whether dataset.ttl's
        obdc:SurfaceableEntity marker is still in sync with it, without
        needing the context-layer facade-resolution machinery that
        created it. See is_dataset_surfaceable_synced.
        """
        source_file: str = str(facade.get("source_file") or "").strip()
        if not source_file:
            return
        source_path: Path = Path(source_file).expanduser().resolve()
        if not source_path.is_file():
            return

        linkset_dir: Path = get_ontobdc_directory(dataset_path) / "linkset"
        linkset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, linkset_dir / "facade.ttl")

        type_ontology_path: Path = source_path.parent / "type.ttl"
        if type_ontology_path.is_file():
            shutil.copyfile(type_ontology_path, linkset_dir / "type.ttl")

    def _build_workbook_contract(
        self,
        facade: Dict[str, Any],
        dataset_path: Path,
    ) -> Dict[str, Any]:
        entity_name: str = str(
            facade.get("entity_name") or ""
        ).strip()
        entity_identifier: str = str(
            facade.get("entity_identifier") or ""
        ).strip()
        if not entity_name or not entity_identifier:
            raise CliCommandArgumentException(
                "The resolved entity facade is incomplete."
            )

        fields: List[EntityWorkbookField] = [
            EntityWorkbookField(
                name=str(field["name"]),
                field_type=self._frictionless_type(
                    str(field.get("datatype", "string"))
                ),
            )
            for field in list(facade.get("fields") or [])
            if str(field.get("name") or "").strip()
        ]
        if not fields:
            raise CliCommandArgumentException(
                "The entity facade does not expose any workbook fields: "
                f"{entity_name}"
            )

        output_dir: Path = dataset_path / "payload" / "document"
        workbook_name: str = f"{entity_identifier}.xlsx"
        worksheet_name: str = entity_name[:31]
        primary_key: List[str] = (
            ["GlobalId"]
            if any(field.name == "GlobalId" for field in fields)
            else []
        )

        return {
            "output_dir": output_dir,
            "workbook_name": workbook_name,
            "workbook_path": output_dir / workbook_name,
            "worksheet_name": worksheet_name,
            "fields": fields,
            "datapackage_path": (
                get_ontobdc_directory(dataset_path) / "datapackage.json"
            ),
            "resource_name": entity_identifier,
            "primary_key": primary_key,
            "entity_uri": str(
                facade.get("entity_uri") or ""
            ).strip(),
            "entity_identifier": entity_identifier,
            "facade_uri": str(
                facade.get("facade_uri") or ""
            ).strip(),
        }

    def _resolve_target_field_name(
        self,
        facade: Dict[str, Any],
    ) -> str:
        requirement_map: Dict[str, bool] = self._load_field_requirement_map(
            facade=facade
        )
        raw_fields: List[Dict[str, Any]] = [
            dict(field)
            for field in list(facade.get("fields") or [])
            if str(field.get("name") or "").strip()
        ]
        if not raw_fields:
            return ""

        field: Dict[str, Any]
        for field in raw_fields:
            field_name: str = str(
                field.get("name") or ""
            ).strip()
            if field_name == "GlobalId":
                continue

            field_identifier: str = str(
                field.get("identifier") or ""
            ).strip()
            if (
                field_identifier
                and requirement_map.get(field_identifier, False)
            ):
                return field_name

        for field in raw_fields:
            field_name = str(field.get("name") or "").strip()
            if field_name and field_name != "GlobalId":
                return field_name

        return ""

    def _load_field_requirement_map(
        self,
        facade: Dict[str, Any],
    ) -> Dict[str, bool]:
        source_file: str = str(
            facade.get("source_file") or ""
        ).strip()
        if not source_file:
            return {}

        source_path: Path = Path(source_file).expanduser().resolve()
        if not source_path.is_file():
            return {}

        graph: Graph = Graph()
        graph.parse(str(source_path), format="turtle")
        requirement_map: Dict[str, bool] = {}
        field_subject: URIRef
        predicate: URIRef
        obj: Any
        for field_subject, predicate, obj in graph:
            predicate_name: str = self._local_name(predicate)
            if predicate_name != "identifier":
                continue
            if not isinstance(obj, Literal):
                continue

            field_identifier: str = str(obj).strip()
            if not field_identifier:
                continue

            requirement_map[field_identifier] = self._is_required_field(
                graph=graph,
                field_subject=field_subject,
            )

        return requirement_map

    def _is_required_field(
        self,
        graph: Graph,
        field_subject: URIRef,
    ) -> bool:
        predicate: URIRef
        obj: Any
        for predicate, obj in graph.predicate_objects(field_subject):
            if self._local_name(predicate) != "isRequired":
                continue
            if isinstance(obj, Literal):
                return bool(obj.toPython())

        return False

    def _local_name(self, predicate: URIRef) -> str:
        predicate_value: str = str(predicate).strip()
        if "#" in predicate_value:
            return predicate_value.rsplit("#", 1)[-1].strip()
        return predicate_value.rstrip("/").rsplit("/", 1)[-1].strip()

    def _frictionless_type(self, datatype: str) -> str:
        return {
            "any_uri": "string",
            "boolean": "boolean",
            "date": "date",
            "date_time": "datetime",
            "dateTime": "datetime",
            "decimal": "number",
            "double": "number",
            "float": "number",
            "integer": "integer",
        }.get(datatype, "string")
