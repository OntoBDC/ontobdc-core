
import os
import subprocess
from typing import List
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.storage import get_storage_file, EMPTY_STORAGE_GRAPH
from ontobdc.storage.adapter.container import StorageRootContainerAdapter
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.storage.plugin.check.is_root_set.hotfix import main as root_set_finish
from ontobdc.cli.domain.response.command import CommandResponse, EnableCommandResponse


class StorageEnableCommand(CliCommandPort):
    """
    Command for enabling the storage component.
    """
    METADATA = CliCommandMetadata(
        id="enable",
        logical_component="storage",
        description="Enable the storage component by installing dependencies and creating the storage file.",
        arguments=[
            {
                "accepts": [
                    "--enable",
                ],
                "description": "Enable the storage component.",
                "usage": "ontobdc storage --enable",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage enable command at the CLI routing stage.
        """
        return len(args) > 1 and args[0] == "storage" and args[1] == "--enable"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log : callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return len(self._request.command_args) == 1 and self._request.command_args[0] == "--enable"

    def run(self) -> CommandResponse:
        """
        Execute the command: install dependencies and create storage.ttl.
        """
        try:
            self._print_info_log("Installing storage dependencies...")
            subprocess.check_call(
                ["pip", "install", "ontobdc[storage]"]
            )
            self._print_info_log("Storage dependencies installed successfully.")

            storage_path: str = get_storage_file()
            if not os.path.exists(os.path.dirname(storage_path)):
                os.makedirs(os.path.dirname(storage_path), exist_ok=True)

            with open(storage_path, "w", encoding="utf-8") as f:
                f.write(EMPTY_STORAGE_GRAPH)

            StorageRootContainerAdapter().save()

            root_set_finish()

            self._print_info_log(f"Storage file created successfully.")

            return EnableCommandResponse(
                success=True,
                title="Storage Component Enabled",
                description="Successfully installed storage dependencies and created the storage index file.",
                content={"success": "Storage component enabled successfully."}
            )
        except Exception as e:
            return EnableCommandResponse(
                success=False,
                title="Failed to Enable Storage Component",
                description=f"An error occurred: {str(e)}",
                content={"error": f"Failed to enable storage: {str(e)}"}
            )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Enable Storage", message)

    def _print_error_log(self, message: str):
        if self._print_log:
            self._print_log("ERROR", "Enable Storage", "Failed to enable storage: " + message)
