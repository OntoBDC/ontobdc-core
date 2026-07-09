
from typing import Optional
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.run.plugin.check.has_valid_context.check import main as check_error
from ontobdc.run.plugin.check.has_valid_context.hotfix import main as plugin_hotfix
from ontobdc.cli.domain.response.command import ExceptionCommandResponse, ReportCommandResponse


class ContextSetParameterCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="set_parameter",
        logical_component="context",
        description="Set a parameter value in the execution context.",
        arguments=[
            {
                "accepts": ["--set"],
                "valued": True,
                "description": "Parameter name to set.",
                "usage": "ontobdc context --set <param_name> --value <param_value>",
            },
            {
                "accepts": ["--value"],
                "valued": True,
                "description": "Parameter value to set.",
                "usage": "ontobdc context --set <param_name> --value <param_value>",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        args = self._request.command_args
        if len(args) != 4:
            return False
        # Check that the arguments are in the correct order
        if not (args[0] == "--set" and args[2] == "--value"):
            return False

        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        return not check_error()

    def run(self) -> ReportCommandResponse | ExceptionCommandResponse:
        try:
            args = self._request.command_args
            param_name = args[1]
            param_value = args[3]

            # Use the context adapter to set the parameter
            self._request.context.set_parameter_value(param_name, param_value)

            return ReportCommandResponse(
                title="Context Parameter Set",
                description=f"Successfully set context parameter '{param_name}' to '{param_value}'.",
                content={
                    "parameter": param_name,
                    "value": param_value,
                },
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="Failed to Set Context Parameter",
                description=f"An error occurred while setting the context parameter: {str(error)}",
                content={
                    "execution_response": str(error),
                },
            )


class ContextUnsetParameterCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="unset_parameter",
        logical_component="context",
        description="Unset a parameter value from the execution context.",
        arguments=[
            {
                "accepts": ["--unset"],
                "valued": True,
                "description": "Parameter name to unset.",
                "usage": "ontobdc context --unset <param_name>",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        args = self._request.command_args
        if not len(args) == 2 and args[0] == "--unset":
            return False

        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        return not check_error()

    def run(self) -> ReportCommandResponse | ExceptionCommandResponse:
        try:
            args = self._request.command_args
            param_name = args[1]

            # Use the context adapter to unset the parameter
            self._request.context.delete_parameter(param_name)

            return ReportCommandResponse(
                title="Context Parameter Unset",
                description=f"Successfully unset context parameter '{param_name}'.",
                content={
                    "parameter": param_name,
                },
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="Failed to Unset Context Parameter",
                description=f"An error occurred while unsetting the context parameter: {str(error)}",
                content={
                    "execution_response": str(error),
                },
            )
