import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, URIRef
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.adapter.repository import EntityContainerInstanceRepository
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookArtifact,
    EntityWorkbookField,
)
from ontobdc.storage.plugin.check.is_container_id_registered.check import (
    get_registered_container_location,
    main as check_container_id_registered,
)


class ContextEntityCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="entity",
        logical_component="context",
        description="Display an entity context, list container instances, or create one in the entity workbook.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Display the persisted information for a context entity.",
                "usage": "ontobdc context --entity <entity_uri>",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "description": "List entity instances for the selected container.",
                "usage": "ontobdc context --container <container_id> --entity <entity>",
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": "Create one entity instance in the selected container workbook.",
                "usage": "ontobdc context --create <instance_name> --container <container_id> --entity <entity>",
            }
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        is_entity_lookup: bool = len(args) == 3 and args[0] == "context" and args[1] == "--entity"
        is_entity_list: bool = (
            len(args) == 5
            and args[0] == "context"
            and "--container" in args
            and "--entity" in args
            and "--create" not in args
        )
        is_entity_create: bool = (
            len(args) == 7
            and args[0] == "context"
            and "--container" in args
            and "--entity" in args
            and "--create" in args
        )
        return is_entity_lookup or is_entity_list or is_entity_create

    def check(self) -> bool:
        if self._is_entity_lookup_request():
            entity_uri: str = str(self._request.context.get_parameter_value("entity_uri") or "").strip()
            if entity_uri:
                return True

            command_args: List[str] = list(self._request.command_args)
            if len(command_args) != 2:
                raise CliCommandArgumentException("Usage: ontobdc context --entity <entity_uri>")

            raw_entity_value: str = str(command_args[1]).strip()
            if not raw_entity_value:
                raise CliCommandArgumentException("Usage: ontobdc context --entity <entity_uri>")

            self._request.context.set_parameter_value("entity_uri", raw_entity_value)
            return True

        container_id, entity_value = self._parse_container_entity_arguments()
        root_path: str = str(self._request.context.root_path).strip()
        if check_container_id_registered(
            container_id=container_id,
            root_path=root_path,
        ) != 0:
            raise CliCommandArgumentException(f"Invalid container: {container_id}")

        container_path: Optional[Path] = get_registered_container_location(
            container_id=container_id,
            root_path=root_path,
        )
        if container_path is None:
            raise CliCommandArgumentException(f"Invalid container: {container_id}")

        facade: Optional[Dict[str, Any]] = EntityVectorRepositoryAdapter(
            root_path=root_path,
        ).resolve_entity_facade(entity_value)
        if facade is None:
            raise CliCommandArgumentException(f"Could not resolve entity facade: {entity_value}")

        self._request.context.set_parameter_value("container_id", container_id)
        self._request.context.set_parameter_value("container_path", str(container_path))
        self._request.context.set_parameter_value("entity", entity_value)
        self._request.context.set_parameter_value("entity_uri", str(facade["entity_uri"]))
        self._request.context.set_parameter_value("entity_facade", facade)

        if self._is_entity_create_request():
            create_value: str = self._parse_create_argument()
            self._request.context.set_parameter_value("create", create_value)

        return True

    def run(self) -> CommandResponse:
        if self._is_entity_lookup_request():
            entity_uri: str = str(self._request.context.get_parameter_value("entity_uri") or "").strip()
            return CommandResponse(
                title="OntoBDC Context Entity",
                description=f"Display the persisted information for entity '{entity_uri}'.",
                content={
                    "entity_uri": entity_uri,
                },
            )

        if self._is_entity_create_request():
            return self._run_create_instance()

        return self._run_list_instances()

    def _is_entity_lookup_request(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        return len(command_args) == 2 and command_args[0] == "--entity"

    def _is_entity_list_request(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        return (
            len(command_args) == 4
            and "--container" in command_args
            and "--entity" in command_args
            and "--create" not in command_args
        )

    def _is_entity_create_request(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        return (
            len(command_args) == 6
            and "--container" in command_args
            and "--entity" in command_args
            and "--create" in command_args
        )

    def _parse_container_entity_arguments(self) -> Tuple[str, str]:
        command_args: List[str] = list(self._request.command_args)
        if len(command_args) not in (4, 6):
            raise CliCommandArgumentException(
                "Usage: ontobdc context --container <container_id> --entity <entity>"
            )

        argument_pairs: Dict[str, str] = {
            command_args[index]: command_args[index + 1]
            for index in range(0, len(command_args), 2)
        }
        container_id: str = str(argument_pairs.get("--container", "")).strip()
        entity_value: str = str(argument_pairs.get("--entity", "")).strip()
        if not container_id or not entity_value:
            raise CliCommandArgumentException(
                "Usage: ontobdc context --container <container_id> --entity <entity>"
            )

        return container_id, entity_value

    def _parse_create_argument(self) -> str:
        command_args: List[str] = list(self._request.command_args)
        if len(command_args) != 6:
            raise CliCommandArgumentException(
                "Usage: ontobdc context --create <instance_name> --container <container_id> --entity <entity>"
            )

        argument_pairs: Dict[str, str] = {
            command_args[index]: command_args[index + 1]
            for index in range(0, len(command_args), 2)
        }
        create_value: str = str(argument_pairs.get("--create", "")).strip()
        if not create_value:
            raise CliCommandArgumentException(
                "Usage: ontobdc context --create <instance_name> --container <container_id> --entity <entity>"
            )

        return create_value

    def _run_list_instances(self) -> CommandResponse:
        facade: Dict[str, Any] = dict(self._request.context.get_parameter_value("entity_facade") or {})
        repository: EntityContainerInstanceRepository = EntityContainerInstanceRepository(
            container_path=str(self._request.context.get_parameter_value("container_path") or "").strip(),
            facade=facade,
        )
        payload: Dict[str, Any] = repository.list_instances()

        return CommandResponse(
            title="Context Entity Instances",
            description=(
                f"Listed {int(payload['instance_count'])} instance(s) of entity '{str(facade.get('entity_name') or '').strip()}' "
                f"in container '{str(self._request.context.get_parameter_value('container_id') or '').strip()}'."
            ),
            content={
                "container_id": str(self._request.context.get_parameter_value("container_id") or "").strip(),
                "container_path": str(self._request.context.get_parameter_value("container_path") or "").strip(),
                "entity": str(payload["entity"]),
                "entity_uri": str(self._request.context.get_parameter_value("entity_uri") or "").strip(),
                "resolution": str(payload["resolution"]),
                "datapackage_path": str(payload["datapackage_path"]),
                "resource_count": int(payload["resource_count"]),
                "resources": list(payload["resources"]),
                "workbook_path": str(payload["workbook_path"]),
                "worksheet_name": str(payload["worksheet_name"]),
                "instance_count": int(payload["instance_count"]),
                "instances": list(payload["instances"]),
            },
        )

    def _run_create_instance(self) -> CommandResponse:
        facade: Dict[str, Any] = dict(self._request.context.get_parameter_value("entity_facade") or {})
        create_value: str = str(self._request.context.get_parameter_value("create") or "").strip()
        workbook_contract: Dict[str, Any] = self._build_workbook_contract(facade=facade)
        adapter: EntityWorkbookAdapter = EntityWorkbookAdapter()
        records: List[Dict[str, Any]] = adapter.read(
            workbook_path=Path(str(workbook_contract["workbook_path"])).expanduser().resolve(),
            worksheet_name=str(workbook_contract["worksheet_name"]),
            fields=list(workbook_contract["fields"]),
        )

        target_field_name: str = self._resolve_target_field_name(facade=facade)
        if not target_field_name:
            raise CliCommandArgumentException("Could not resolve a writable entity field.")

        new_record: Dict[str, Any] = {
            field.name: ""
            for field in list(workbook_contract["fields"])
        }
        if "GlobalId" in new_record:
            new_record["GlobalId"] = str(uuid.uuid4())
        new_record[target_field_name] = create_value
        records.append(new_record)

        artifact: EntityWorkbookArtifact = adapter.generate(
            output_dir=Path(str(workbook_contract["output_dir"])).expanduser().resolve(),
            workbook_name=str(workbook_contract["workbook_name"]),
            worksheet_name=str(workbook_contract["worksheet_name"]),
            fields=list(workbook_contract["fields"]),
            records=records,
            datapackage_path=Path(str(workbook_contract["datapackage_path"])).expanduser().resolve(),
            package_name="ontobdc_container",
            resource_name=str(workbook_contract["resource_name"]),
            primary_key=list(workbook_contract["primary_key"]),
            entity_uri=str(workbook_contract["entity_uri"]),
            entity_identifier=str(workbook_contract["entity_identifier"]),
            facade_uri=str(workbook_contract["facade_uri"]),
        )

        return CommandResponse(
            title="Context Entity Created",
            description=(
                f"Created one instance of entity '{str(facade.get('entity_name') or '').strip()}' "
                f"in container '{str(self._request.context.get_parameter_value('container_id') or '').strip()}'."
            ),
            content={
                "container_id": str(self._request.context.get_parameter_value("container_id") or "").strip(),
                "container_path": str(self._request.context.get_parameter_value("container_path") or "").strip(),
                "entity": str(facade.get("entity_name") or "").strip(),
                "entity_uri": str(self._request.context.get_parameter_value("entity_uri") or "").strip(),
                "target_field": target_field_name,
                "created_value": create_value,
                "workbook_path": str(artifact.workbook_path),
                "worksheet_name": artifact.worksheet_name,
                "datapackage_path": str(artifact.datapackage_path),
                "instance_count": artifact.generated_row_count,
                "validation": artifact.validation,
            },
        )

    def _build_workbook_contract(self, facade: Dict[str, Any]) -> Dict[str, Any]:
        container_path: Path = Path(
            str(self._request.context.get_parameter_value("container_path") or "").strip()
        ).expanduser().resolve()
        entity_name: str = str(facade.get("entity_name") or "").strip()
        entity_identifier: str = str(facade.get("entity_identifier") or "").strip()
        if not entity_name or not entity_identifier:
            raise CliCommandArgumentException("The resolved entity facade is incomplete.")

        fields: List[EntityWorkbookField] = [
            EntityWorkbookField(
                name=str(field["name"]),
                field_type=self._frictionless_type(str(field.get("datatype", "string"))),
            )
            for field in list(facade.get("fields") or [])
            if str(field.get("name") or "").strip()
        ]
        if not fields:
            raise CliCommandArgumentException(f"The entity facade does not expose any workbook fields: {entity_name}")

        output_dir: Path = container_path / "payload" / "document"
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
            "datapackage_path": container_path / ".__ontobdc__" / "datapackage.json",
            "resource_name": entity_identifier,
            "primary_key": primary_key,
            "entity_uri": str(facade.get("entity_uri") or "").strip(),
            "entity_identifier": entity_identifier,
            "facade_uri": str(facade.get("facade_uri") or "").strip(),
        }

    def _resolve_target_field_name(self, facade: Dict[str, Any]) -> str:
        requirement_map: Dict[str, bool] = self._load_field_requirement_map(facade=facade)
        raw_fields: List[Dict[str, Any]] = [
            dict(field)
            for field in list(facade.get("fields") or [])
            if str(field.get("name") or "").strip()
        ]
        if not raw_fields:
            return ""

        field: Dict[str, Any]
        for field in raw_fields:
            field_name: str = str(field.get("name") or "").strip()
            if field_name == "GlobalId":
                continue

            field_identifier: str = str(field.get("identifier") or "").strip()
            if field_identifier and requirement_map.get(field_identifier, False):
                return field_name

        for field in raw_fields:
            field_name = str(field.get("name") or "").strip()
            if field_name and field_name != "GlobalId":
                return field_name

        return ""

    def _load_field_requirement_map(self, facade: Dict[str, Any]) -> Dict[str, bool]:
        source_file: str = str(facade.get("source_file") or "").strip()
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

    def _is_required_field(self, graph: Graph, field_subject: URIRef) -> bool:
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
