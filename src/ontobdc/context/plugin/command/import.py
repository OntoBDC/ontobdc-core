
from pathlib import Path
from typing import Dict, List
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.storage.plugin.check.is_container_id_registered.check import (
    get_registered_container_location,
    main as check_container_id_registered,
)


class DocumentImportCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="import",
        logical_component="context",
        description="Import a file into an OntoBDC container for a resolved RDF linkset.",
        arguments=[
            {
                "accepts": ["--container-id"],
                "valued": True,
                "description": "Select the target storage container identifier.",
                "usage": "ontobdc context --container-id <container_id> --entity <entity_uri> --import-from <file_path>",
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Target entity URI for the learning flow.",
                "usage": "ontobdc context --container-id <container_id> --entity <entity_uri> --import-from <file_path>",
            },
            {
                "accepts": ["--import-from"],
                "valued": True,
                "description": "Select the source file to be imported into the container.",
                "usage": "ontobdc context --entity <entity_uri> --import-from <file_path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 7
            and args[0] == "context"
            and "--container-id" in args
            and "--entity" in args
            and "--import-from" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)

        argument_pairs: Dict[str, str] = {
            args[index]: args[index + 1]
            for index in range(0, len(args), 2)
        }

        container_id: str = str(argument_pairs.get("--container-id", "")).strip()
        if not container_id:
            return False
        if check_container_id_registered(
            container_id=container_id,
            root_path=str(self._request.context.root_path),
        ) != 0:
            raise CliCommandArgumentException(f"Invalid container_id: {container_id}")

        container_path: Optional[Path] = get_registered_container_location(
            container_id=container_id,
            root_path=str(self._request.context.root_path),
        )
        if container_path is None:
            raise CliCommandArgumentException(f"Invalid container_id: {container_id}")

        resolved_entity_value: str = str(
            self._request.context.get_parameter_value("entity_uri") or ""
        ).strip()
        if not resolved_entity_value:
            return False

        resolved_import_value: str = str(
            self._request.context.get_parameter_value("import_from_path") or ""
        ).strip()
        if not resolved_import_value:
            return False

        self._request.context.set_parameter_value("container_id", container_id)
        self._request.context.set_parameter_value("container_path", str(container_path))

        resolved_import_path: Path = Path(resolved_import_value).expanduser()
        if not resolved_import_path.exists():
            return False

        return True

    def run(self) -> CommandResponse:
        from ontobdc.context.adapter.document import DocumentImportStateTransitionHandler

        handler: DocumentImportStateTransitionHandler = DocumentImportStateTransitionHandler(
            context=self._request.context,
        )

        return handler.execute()
