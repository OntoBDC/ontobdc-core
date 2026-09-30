from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.etl import EtlEventContextKeys, EtlEventPayloadKeys

from ontobdc.context.plugin.machine.pdf_to_graph.machine import (
    PdfToGraphStateTransitionHandler,
)


class ContextPdfToGraphCommand(CliCommandPort):
    """Run the full PDF-to-knowledge-graph FSM pipeline in the context domain."""

    COMPONENT: ClassVar[str] = "context"
    EXECUTABLE: ClassVar[str] = "ontobdc"
    LOGICAL_COMPONENT: ClassVar[str] = "context"
    COMMAND_ID: ClassVar[str] = "pdf_to_graph"
    OUTPUT_DIR_CONTEXT_KEY: ClassVar[str] = EtlEventContextKeys.CONTAINER_PATH

    METADATA: ClassVar[CliCommandMetadata] = CliCommandMetadata(
        id=COMMAND_ID,
        logical_component=LOGICAL_COMPONENT,
        description=(
            "Run the full PDF-to-knowledge-graph pipeline: verify "
            "text readiness, then extract positioned text blocks from the PDF."
        ),
        arguments=[
            {
                "accepts": ["--pdf-to-graph"],
                "valued": True,
                "required": True,
                "description": (
                    "Path to the PDF file to feed into the "
                    "PDF-to-knowledge-graph pipeline. The pipeline "
                    "verifies text readiness and then extracts "
                    "positioned text blocks from the PDF."
                ),
            },
            {
                "accepts": ["--output-path"],
                "valued": True,
                "required": False,
                "description": (
                    "Directory where the ETL payloads produced by the "
                    "pipeline will be written. When omitted, the "
                    "pipeline writes into the standard ETL directory "
                    "contract resolved from the project container."
                ),
            },
        ],
    )

    @staticmethod
    def _usage_message() -> str:
        return (
            f"Usage: {ContextPdfToGraphCommand.EXECUTABLE} "
            f"{ContextPdfToGraphCommand.COMPONENT} "
            f"--pdf-to-graph <pdf_path> [--output-path <dir>]"
        )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ContextPdfToGraphCommand.COMPONENT:
            return False
        if len(args) == 3 and args[1] == "--pdf-to-graph":
            return True
        if len(args) == 5 and args[1] == "--pdf-to-graph" and args[3] == "--output-path":
            return True
        return False

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        source_path, output_path = self._parse_arguments()

        if not source_path.exists() or not source_path.is_file():
            raise CliCommandArgumentException(
                f"Invalid PDF path: {source_path}. "
                f"File was not found. Current working directory is: {Path.cwd()}"
            )
        if source_path.suffix.lower() != ".pdf":
            raise CliCommandArgumentException(
                f"PDF-to-graph supports only PDF files. Got '{source_path.suffix or '<none>'}'."
            )

        self._request.context.set_parameter_value(
            EtlEventPayloadKeys.SOURCE_PATH,
            str(source_path),
        )

        if output_path is not None:
            target_dir: Path = type(self)._resolve_output_dir(
                output_path=output_path,
            )
            if not target_dir.exists() or not target_dir.is_dir():
                raise CliCommandArgumentException(
                    f"Invalid output directory: {target_dir}. "
                    f"Directory does not exist or is not a folder."
                )
            self._request.context.set_parameter_value(
                self.OUTPUT_DIR_CONTEXT_KEY,
                str(target_dir),
            )

        return True

    def run(self) -> CommandResponse:
        handler = PdfToGraphStateTransitionHandler(
            context=self._request.context,
            logger=getattr(self._request, "logger", None),
        )
        return handler.execute()

    def _parse_arguments(self) -> Tuple[Path, Optional[Path]]:
        command_args: List[str] = list(self._request.command_args)
        if (
            (len(command_args) != 2 and len(command_args) != 4)
            or command_args[0] != "--pdf-to-graph"
        ):
            raise CliCommandArgumentException(
                type(self)._usage_message()
            )

        raw_source: str = str(command_args[1]).strip()
        if not raw_source:
            raise CliCommandArgumentException(
                type(self)._usage_message()
            )

        source_path: Path = Path(raw_source).expanduser().resolve()

        output_path: Optional[Path] = None
        if len(command_args) == 4:
            if command_args[2] != "--output-path":
                raise CliCommandArgumentException(
                    type(self)._usage_message()
                )
            raw_output: str = str(command_args[3]).strip()
            if not raw_output:
                raise CliCommandArgumentException(
                    type(self)._usage_message()
                )
            output_path = Path(raw_output).expanduser().resolve()

        return source_path, output_path

    @staticmethod
    def _resolve_output_dir(output_path: Path) -> Path:
        if output_path.is_dir():
            return output_path
        return output_path.parent
