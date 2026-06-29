import os
import shutil
from typing import Dict, List, Optional

from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import ExceptionCommandResponse, ReportCommandResponse
from ontobdc.context import get_context_file
from ontobdc.run.plugin.check.has_valid_context.check import main as check_error
from ontobdc.run.plugin.check.has_valid_context.hotfix import main as plugin_hotfix
from ontobdc.run.domain.machine.response import IntentScoreResponse


def to_config_relative_path(file_path: str) -> str:
    config_dir_path: str = str(ConfigDataAdapter().config_dir)
    return f"./{file_path.split(config_dir_path)[-1].strip('/')}"


def _context_timestamp(context_file_path: str) -> str:
    context_stat: os.stat_result = os.stat(context_file_path)
    created_at_timestamp: float = getattr(context_stat, "st_birthtime", context_stat.st_ctime)
    return str(int(created_at_timestamp))


def context_source_file_paths(context_file_path: str) -> List[str]:
    context_dir_path: str = os.path.dirname(context_file_path)
    return [
        context_file_path,
        os.path.join(context_dir_path, IntentScoreResponse.PARSED_INTENT_FILE_NAME),
        os.path.join(context_dir_path, IntentScoreResponse.CANONICALIZED_INTENT_FILE_NAME),
    ]


def save_context_snapshot(context_file_path: str) -> Dict[str, object]:
    destination_dir_path: str = os.path.join(
        str(ConfigDataAdapter().config_dir),
        "memory",
        f"context-{_context_timestamp(context_file_path)}",
    )
    source_file_paths: List[str] = context_source_file_paths(context_file_path)

    os.makedirs(destination_dir_path, exist_ok=True)

    copied_files: List[str] = []
    for source_file_path in source_file_paths:
        if not os.path.isfile(source_file_path):
            raise FileNotFoundError(f"Context file not found: {source_file_path}")

        destination_file_path: str = os.path.join(destination_dir_path, os.path.basename(source_file_path))
        shutil.copy2(source_file_path, destination_file_path)
        copied_files.append(to_config_relative_path(destination_file_path))

    return {
        "directory": to_config_relative_path(destination_dir_path),
        "files": copied_files,
    }


class ContextSaveCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="snapshot",
        logical_component="context",
        description="Save the persisted execution context files.",
        arguments=[
            {
                "accepts": ["--snapshot"],
                "description": "Save the persisted execution context files to memory/context-<timestamp>.",
            }
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        if not self._request.command_args == ["--snapshot"]:
            return False

        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        return not check_error()

    def run(self) -> ReportCommandResponse | ExceptionCommandResponse:
        try:
            context_file_path: str = get_context_file()
            saved_context: Dict[str, object] = save_context_snapshot(context_file_path)
            return ReportCommandResponse(
                title="OntoBDC Context",
                description="Persisted execution context files were saved.",
                content={
                    "saved_context": saved_context,
                },
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="OntoBDC Context",
                description="Failed to save the persisted execution context files.",
                content={
                    "execution_response": str(error),
                },
            )
