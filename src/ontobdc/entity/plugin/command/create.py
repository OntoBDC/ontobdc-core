import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookArtifact,
    EntityWorkbookField,
)


class EntityCreateCommand(CliCommandPort):
    """Create a named entity element from its RDF facade."""

    METADATA = CliCommandMetadata(
        id="entity_create",
        logical_component="entity",
        description="Create a named element in an entity workbook.",
        arguments=[
            {
                "accepts": ["--container-id"],
                "valued": True,
                "description": "Select the target OntoBDC container.",
                "usage": (
                    "ontobdc entity [--container-id <container_id>] "
                    "--entity <entity> --create <name>"
                ),
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Select the entity class to instantiate.",
                "usage": (
                    "ontobdc entity [--container-id <container_id>] "
                    "--entity <entity> --create <name>"
                ),
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": "Set the initial name of the new element.",
                "usage": (
                    "ontobdc entity [--container-id <container_id>] "
                    "--entity <entity> --create <name>"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) in (5, 7)
            and args[0] == "entity"
            and "--entity" in args
            and "--create" in args
            and (
                "--container-id" in args
                if len(args) == 7
                else "--container-id" not in args
            )
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        container_id = self._context_value("container_id")
        entity = self._context_value("entity")
        element_name = self._context_value("create")
        if not container_id or not entity or not element_name:
            return False

        container_path = self._get_registered_container_location(
            container_id=container_id,
            root_path=str(self._request.context.root_path),
        )
        if container_path is None:
            return False

        facade = self._resolve_entity_facade(
            entity=entity,
            root_path=str(self._request.context.root_path),
        )
        if facade is None:
            return False

        self._request.context.set_parameter_value("container_path", str(container_path))
        self._request.context.set_parameter_value("entity_facade", facade)
        return True

    def run(self) -> CommandResponse:
        container_id = str(
            self._request.context.get_parameter_value("container_id")
        )
        element_name = str(
            self._request.context.get_parameter_value("create")
        )
        facade: Dict[str, Any] = self._request.context.get_parameter_value(
            "entity_facade"
        )
        container_path = Path(
            str(self._request.context.get_parameter_value("container_path"))
        ).expanduser().resolve()

        entity_name = str(facade["entity_name"])
        entity_identifier = str(facade["entity_identifier"])
        fields = [
            EntityWorkbookField(
                str(field["name"]),
                self._frictionless_type(str(field.get("datatype", "string"))),
            )
            for field in facade["fields"]
        ]
        workbook_name = (
            "workstreams.xlsx"
            if entity_name == "WorkStream"
            else f"{self._pluralize(entity_identifier)}.xlsx"
        )
        worksheet_name = entity_name[:31]
        resource_name = entity_identifier
        output_dir = container_path / "payload" / "document"
        workbook_path = output_dir / workbook_name
        adapter = EntityWorkbookAdapter()
        records = adapter.read(
            workbook_path=workbook_path,
            worksheet_name=worksheet_name,
            fields=fields,
        )
        global_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{container_id}:{entity_identifier}:{element_name}",
            )
        )
        if not any(
            str(record.get("GlobalId") or "").strip() == global_id
            for record in records
        ):
            record = {field.name: "" for field in fields}
            if "GlobalId" in record:
                record["GlobalId"] = global_id
            if "Name" in record:
                record["Name"] = element_name
            records.append(record)

        primary_key = ["GlobalId"] if any(
            field.name == "GlobalId" for field in fields
        ) else []
        artifact: EntityWorkbookArtifact = adapter.generate(
            output_dir=output_dir,
            workbook_name=workbook_name,
            worksheet_name=worksheet_name,
            fields=fields,
            records=records,
            datapackage_path=container_path / ".__ontobdc__" / "datapackage.json",
            package_name="ontobdc_container",
            resource_name=resource_name,
            primary_key=primary_key,
            entity_uri=self._uri_value(facade.get("entity_uri")),
            entity_identifier=entity_identifier,
            facade_uri=self._uri_value(facade.get("facade_uri")),
        )

        content = {
            "container_id": container_id,
            "entity": entity_name,
            "entity_uri": facade["entity_uri"],
            "element_id": global_id,
            "element_name": element_name,
            "workbook_path": str(artifact.workbook_path),
            "datapackage_path": str(artifact.datapackage_path),
            "entity_count": artifact.generated_row_count,
        }
        if entity_name == "WorkStream":
            content["work_stream_count"] = artifact.generated_row_count

        return CommandResponse(
            title="Entity Creation",
            description=f"Created the {entity_name} entry and generated its workbook.",
            content=content,
        )

    def _resolve_entity_facade(
        self,
        *,
        entity: str,
        root_path: str,
    ) -> Optional[Dict[str, Any]]:
        normalized = entity.strip().lower().replace("_", "")
        if normalized == "workstream" or normalized.endswith("#workstream"):
            return {
                "entity_uri": entity,
                "entity_name": "WorkStream",
                "entity_identifier": "work_stream",
                "facade_uri": "",
                "fields": [
                    {"name": name, "datatype": "string"}
                    for name in (
                        "GlobalId",
                        "Description",
                        "Name",
                        "What",
                        "Why",
                        "Who",
                        "Where",
                        "When",
                        "How",
                        "HowMuch",
                    )
                ],
                "source_file": "",
            }
        return EntityVectorRepositoryAdapter(
            root_path=root_path
        ).resolve_entity_facade(entity)

    def _frictionless_type(self, datatype: str) -> str:
        return {
            "boolean": "boolean",
            "date": "date",
            "dateTime": "datetime",
            "decimal": "number",
            "double": "number",
            "float": "number",
            "integer": "integer",
        }.get(datatype, "string")

    def _pluralize(self, identifier: str) -> str:
        if identifier.endswith("s"):
            return identifier
        if identifier.endswith(("ch", "sh", "x", "z")):
            return f"{identifier}es"
        if identifier.endswith("y") and len(identifier) > 1:
            return f"{identifier[:-1]}ies"
        return f"{identifier}s"

    def _uri_value(self, value: Any) -> str:
        normalized = str(value or "").strip()
        if normalized.startswith("urn:") or "://" in normalized:
            return normalized
        return ""

    def _get_registered_container_location(
        self,
        *,
        container_id: str,
        root_path: str,
    ) -> Optional[Path]:
        from ontobdc.storage.plugin.check.is_container_id_registered.check import (
            get_registered_container_location,
        )

        return get_registered_container_location(
            container_id=container_id,
            root_path=root_path,
        )

    def _context_value(self, key: str) -> Optional[str]:
        value = self._request.context.get_parameter_value(key)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None
