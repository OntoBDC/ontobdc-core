from pathlib import Path
from typing import Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import ExceptionCommandResponse, CommandResponse
from ontobdc.context.domain.machine.document_import_state import DocumentImportProcessState
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort


class DocumentImportStateTransitionHandler:
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()

    @property
    def context(self) -> CliContextPort:
        return self._context

    def execute(self) -> CommandResponse:
        return ExceptionCommandResponse(
            title="Context Document Import Incomplete",
            description="The document import state transition handler scaffold is defined but not implemented yet.",
            content={
                "container_id": str(self._context.get_parameter_value("container_id") or "").strip(),
                "container_path": str(self._context.get_parameter_value("container_path") or "").strip(),
                "entity_uri": str(self._context.get_parameter_value("entity_uri") or "").strip(),
                "source_path": str(self._context.get_parameter_value("import_from_path") or "").strip(),
                "current_state": DocumentImportProcessState.UNDEFINED.value,
                "statechart_file": str(
                    Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_document_import.yaml"
                ),
            },
        )
