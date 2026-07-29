import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookArtifact,
    EntityWorkbookField,
)
class EntityCreateCommand(CliCommandPort):
    """Create a named entity element and maintain its workbook."""

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
                    "--entity WorkStream --create <name>"
                ),
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Select the entity class to instantiate.",
                "usage": (
                    "ontobdc entity [--container-id <container_id>] "
                    "--entity WorkStream --create <name>"
                ),
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": "Set the initial name of the new element.",
                "usage": (
                    "ontobdc entity [--container-id <container_id>] "
                    "--entity WorkStream --create <name>"
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
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        container_id: Optional[str] = self._context_value("container_id")
        entity: Optional[str] = self._context_value("entity")
        element_name: Optional[str] = self._context_value("create")
        if not container_id or not entity or not element_name:
            return False
        if not self._is_work_stream(entity):
            return False

        container_path: Optional[Path] = self._get_registered_container_location(
            container_id=container_id,
            root_path=str(self._request.context.root_path),
        )
        if container_path is None:
            return False

        self._request.context.set_parameter_value(
            "container_path",
            str(container_path),
        )
        return True

    def run(self) -> CommandResponse:
        container_id: str = str(
            self._request.context.get_parameter_value("container_id")
        )
        entity: str = str(
            self._request.context.get_parameter_value("entity")
        )
        element_name: str = str(
            self._request.context.get_parameter_value("create")
        )
        container_path = Path(
            str(self._request.context.get_parameter_value("container_path"))
        ).expanduser().resolve()
        output_dir: Path = container_path / "payload" / "document"
        workbook_path: Path = output_dir / "workstreams.xlsx"
        fields: List[EntityWorkbookField] = self._work_stream_fields()
        adapter = EntityWorkbookAdapter()
        records: List[Dict[str, Any]] = adapter.read(
            workbook_path=workbook_path,
            worksheet_name="WorkStream",
            fields=fields,
        )
        global_id: str = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{container_id}:workstream:{element_name}",
            )
        )
        if not any(
            str(record.get("GlobalId") or "").strip() == global_id
            for record in records
        ):
            records.append(
                {
                    "GlobalId": global_id,
                    "Description": "",
                    "Name": element_name,
                    "What": "",
                    "Why": "",
                    "Who": "",
                    "Where": "",
                    "When": "",
                    "How": "",
                    "HowMuch": "",
                }
            )

        artifact: EntityWorkbookArtifact = adapter.generate(
            output_dir=output_dir,
            workbook_name=workbook_path.name,
            worksheet_name="WorkStream",
            fields=fields,
            records=records,
            datapackage_path=container_path / ".__ontobdc__" / "datapackage.json",
            package_name="ontobdc_container",
            resource_name="work_stream",
            primary_key=["GlobalId"],
        )

        return CommandResponse(
            title="Entity Creation",
            description="Created the WorkStream entry and generated its workbook.",
            content={
                "container_id": container_id,
                "entity": entity,
                "element_id": global_id,
                "element_name": element_name,
                "workbook_path": str(artifact.workbook_path),
                "datapackage_path": str(artifact.datapackage_path),
                "work_stream_count": artifact.generated_row_count,
            },
        )

    def _work_stream_fields(self) -> List[EntityWorkbookField]:
        return [
            EntityWorkbookField("GlobalId"),
            EntityWorkbookField("Description"),
            EntityWorkbookField("Name"),
            EntityWorkbookField("What"),
            EntityWorkbookField("Why"),
            EntityWorkbookField("Who"),
            EntityWorkbookField("Where"),
            EntityWorkbookField("When"),
            EntityWorkbookField("How"),
            EntityWorkbookField("HowMuch"),
        ]

    def _is_work_stream(self, entity: str) -> bool:
        normalized: str = entity.strip().lower().replace("_", "")
        return normalized == "workstream" or normalized.endswith("#workstream")

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
        value: object = self._request.context.get_parameter_value(key)
        if value is None:
            return None
        normalized: str = str(value).strip()
        return normalized or None
