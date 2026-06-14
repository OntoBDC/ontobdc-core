import os
from typing import Dict, Optional

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.run.plugin.check.has_valid_context.check import main as check_error
from ontobdc.run.plugin.check.has_valid_context.hotfix import main as plugin_hotfix
from ontobdc.cli.domain.resource.command import ExceptionCommandResponse, ReportCommandResponse
from ontobdc.context import get_context_file
from ontobdc.context.plugin.command.snapshot import (
    context_source_file_paths,
    save_context_snapshot,
    to_config_relative_path,
)


class ContextClearCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="clear",
        logical_component="context",
        description="Save and clear the persisted execution context files.",
        arguments=[
            {
                "accepts": ["--clear"],
                "description": "Save the persisted execution context files and then remove them.",
            }
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        if not self._request.command_args == ["--clear"]:
            return False

        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        return not check_error()

    def run(self) -> ReportCommandResponse | ExceptionCommandResponse:
        try:
            context_file_path: str = get_context_file()
            saved_context: Dict[str, object] = save_context_snapshot(context_file_path)
            cleared_files: list[str] = self._clear_context_files(context_file_path)

            return ReportCommandResponse(
                title="OntoBDC Context",
                description="Persisted execution context files were saved and removed.",
                content={
                    "saved_context": saved_context,
                    "cleared_context": {
                        "files": cleared_files,
                    },
                },
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="OntoBDC Context",
                description="Failed to clear the persisted execution context files.",
                content={
                    "execution_response": str(error),
                },
            )

    def _clear_context_files(self, context_file_path: str) -> list[str]:
        cleared_files: list[str] = []
        for source_file_path in context_source_file_paths(context_file_path):
            if not os.path.isfile(source_file_path):
                raise FileNotFoundError(f"Context file not found: {source_file_path}")

            os.remove(source_file_path)
            cleared_files.append(to_config_relative_path(source_file_path))

        return cleared_files
