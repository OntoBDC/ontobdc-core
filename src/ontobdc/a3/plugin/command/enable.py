import subprocess

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse, EnableCommandResponse


class A3EnableCommand(CliCommandPort):
    """
    Command for enabling the A3 component.
    """
    METADATA = CliCommandMetadata(
        id="enable",
        logical_component="a3",
        description="Enable the A3 component by installing its dependencies.",
        arguments=[
            {
                "accepts": [
                    "--enable",
                ],
                "description": "Enable the A3 component.",
                "usage": "ontobdc a3 --enable",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return True

    def run(self) -> CommandResponse:
        """
        Execute the command: install A3 dependencies.
        """
        try:
            self._print_info_log("Installing A3 dependencies...")
            subprocess.check_call(
                ["pip", "install", "ontobdc[a3]"]
            )
            self._print_info_log("A3 dependencies installed successfully.")

            return EnableCommandResponse(
                success=True,
                title="A3 Component Enabled",
                description="Successfully installed A3 dependencies.",
                content={"success": "A3 component enabled successfully."}
            )
        except Exception as e:
            return EnableCommandResponse(
                success=False,
                title="Failed to Enable A3 Component",
                description=f"An error occurred: {str(e)}",
                content={"error": f"Failed to enable A3: {str(e)}"}
            )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Enable A3", message)

    def _print_error_log(self, message: str):
        if self._print_log:
            self._print_log("ERROR", "Enable A3", "Failed to enable A3: " + message)
