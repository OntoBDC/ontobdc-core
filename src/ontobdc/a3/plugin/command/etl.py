
from typing import Callable, Optional

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.a3.adapter.etl import A3EtlStartResult, A3EtlStarterAdapter
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, ExceptionCommandResponse


class A3EtlCommand(CliCommandPort):
    """
    Boilerplate command for the A3 ETL flow.
    """
    METADATA = CliCommandMetadata(
        id="etl",
        logical_component="a3",
        description="Start the A3 ETL flow.",
        arguments=[
            {
                "accepts": [
                    "--etl",
                ],
                "description": "Start the A3 ETL flow.",
                "usage": "ontobdc a3 --etl --source <file|url>",
            },
            {
                "accepts": [
                    "--source",
                ],
                "valued": True,
                "description": "Source file path or URL to be processed by the ETL flow.",
                "usage": "ontobdc a3 --etl --source <file|url>",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[Callable[..., None]] = None

    def set_print_log(self, print_log: Callable[..., None]) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        """
        return (
            len(self._request.command_args) == 3
            and self._request.command_args[0] == "--etl"
            and self._request.command_args[1] == "--source"
            and isinstance(self._request.command_args[2], str)
            and bool(self._request.command_args[2].strip())
        )

    def run(self) -> CommandResponse:
        """
        Start the A3 ETL flow through the dedicated adapter.
        """
        self._request.context.delete_parameter("etl_shape_uri")
        source_value: str = self._request.command_args[2].strip()
        starter: A3EtlStarterAdapter = A3EtlStarterAdapter()

        try:
            result: A3EtlStartResult = starter.start(source_value, self._request.context.root_path)
        except FileNotFoundError as e:
            return ExceptionCommandResponse(
                title="OntoBDC A3 ETL",
                description="Incoming resource not found.",
                content={
                    "execution_response": str(e),
                },
            )
        except NotImplementedError as e:
            return ExceptionCommandResponse(
                title="OntoBDC A3 ETL",
                description="Incoming resource type is not supported yet.",
                content={
                    "execution_response": str(e),
                },
            )
        except ValueError as e:
            return ExceptionCommandResponse(
                title="OntoBDC A3 ETL",
                description="Failed to initialize the A3 ETL process.",
                content={
                    "execution_response": str(e),
                },
            )
        except Exception as e:
            return ExceptionCommandResponse(
                title="OntoBDC A3 ETL",
                description="Unexpected error while initializing the A3 ETL process.",
                content={
                    "execution_response": str(e),
                },
            )

        for key in ("resource_location", "package_path", "dataset_id", "container_id"):
            value: Optional[str] = result.get(key)
            if value is not None:
                self._request.context.set_parameter_value(key, value)

        return CommandResponse(
            title="OntoBDC A3 ETL",
            description="A3 ETL process initialized successfully.",
            content={
                "command": "ontobdc a3 --etl",
                **result,
            },
        )
