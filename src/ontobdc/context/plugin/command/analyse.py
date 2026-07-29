from pathlib import Path
from typing import List

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.context.adapter.machine import EntityAnalysisStateTransitionHandler
from ontobdc.context.adapter.repository import EntityAnalysisStepRepository


class ContextAnalyseCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="analyse",
        logical_component="context",
        description="Analyse a file and infer its closest entity type.",
        arguments=[
            {
                "accepts": ["--analyse"],
                "valued": True,
                "description": "Analyse a source file against the available entity vectors.",
                "usage": "ontobdc context --analyse <file_path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 3 and args[0] == "context" and args[1] == "--analyse"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        source_path: Path = self._parse_argument()
        if not source_path.exists() or not source_path.is_file():
            raise CliCommandArgumentException(f"Invalid analyse path: {source_path}")
        if source_path.suffix.lower() != ".pdf":
            raise CliCommandArgumentException(
                f"Context analysis currently supports only PDF files. Got '{source_path.suffix or '<none>'}'."
            )

        self._request.context.set_parameter_value("analyse_source_path", str(source_path))
        return True

    def run(self) -> CommandResponse:
        source_path: str = str(self._request.context.get_parameter_value("analyse_source_path")).strip()
        try:
            step_repository = EntityAnalysisStepRepository(
                root_path=str(self._request.context.root_path),
                source_path=source_path,
            )
            self._request.context.set_parameter_value("step_repository", step_repository)
            response: CommandResponse = EntityAnalysisStateTransitionHandler(
                context=self._request.context,
            ).execute()
            return response
        except Exception as exc:
            return ExceptionCommandResponse(
                title="Context Entity Analysis Failed",
                description=f"Could not analyse '{source_path}'.",
                content={
                    "source_path": source_path,
                    "error": str(exc),
                },
            )

    def _parse_argument(self) -> Path:
        command_args: List[str] = list(self._request.command_args)
        if len(command_args) != 2 or command_args[0] != "--analyse":
            raise CliCommandArgumentException("Usage: ontobdc context --analyse <file_path>")

        source_path: str = str(command_args[1]).strip()
        if not source_path:
            raise CliCommandArgumentException("Usage: ontobdc context --analyse <file_path>")

        return Path(source_path).expanduser().resolve()
