from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import TreeCommandResponse
from ontobdc.container.plugin.capability.loader.container import (
    StorageContainerDataLoaderCapability,
)


class StorageContainerInspectCommand(CliCommandPort):
    """
    Command for inspecting a registered container.

    This command owns exactly one surface: the static, pipe-friendly,
    tree-text response rendered through the standard CLI response
    pipeline. The interactive Textual tree viewer lives in its own
    command class (StorageContainerInteractiveInspectCommand) so that
    each command keeps a single responsibility and a single response
    contract.
    """
    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_inspect",
        logical_component="container",
        description="Inspect a registered container.",
        arguments=[
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select which container to inspect, by storage "
                    "identifier. When omitted, the container is resolved "
                    "from the current working directory. Inspection "
                    "returns the container's registered metadata plus a "
                    "tree summarizing its linkset and datasets."
                ),
            },
            {
                "accepts": ["--inspect"],
                "description": (
                    "Print the container's registered metadata along "
                    "with a static tree summarizing its linkset and "
                    "datasets."
                ),
            },
        ],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    INSPECT_FLAGS: ClassVar[List[str]] = ["--inspect"]
    CONTAINER_FLAG: ClassVar[str] = "--container"
    INTERACTIVE_FLAGS: ClassVar[List[str]] = ["--interactive", "-i"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container inspection command at the CLI routing stage.
        """
        if not args or args[0] != "container":
            return False

        return StorageContainerInspectCommand._matches(args[1:])

    def check(self) -> bool:
        """
        Validate the scoped arguments and bind the selected container id.
        """
        if not self._matches(self._request.command_args):
            return False

        container_id: Any = self._request.context.get_parameter_value(
            "container_id"
        )
        return isinstance(container_id, str) and bool(container_id.strip())

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are a --inspect request for the
        STATIC surface only.

        Mutually exclusive with StorageContainerInteractiveInspectCommand:
        this matcher rejects inputs that carry --interactive (or its short
        alias -i) because that presentation mode is the sole responsibility
        of the dedicated interactive command.
        """
        if not any(flag in scoped_args for flag in StorageContainerInspectCommand.INSPECT_FLAGS):
            return False

        if any(flag in scoped_args for flag in StorageContainerInspectCommand.INTERACTIVE_FLAGS):
            return False

        remaining: List[str] = list(scoped_args)
        for inspect_flag in StorageContainerInspectCommand.INSPECT_FLAGS:
            if inspect_flag in remaining:
                remaining.remove(inspect_flag)
                break
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == StorageContainerInspectCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> TreeCommandResponse:
        """
        Load and return the selected container data as a static tree.
        """
        container_id_value: Any = self._request.context.get_parameter_value(
            "container_id"
        )
        if not isinstance(container_id_value, str):
            raise TypeError(
                "Container id must be a string, got "
                f"{type(container_id_value).__name__}."
            )

        container_id: str = container_id_value.strip()
        if not container_id:
            raise ValueError("Container id cannot be empty.")

        capability: StorageContainerDataLoaderCapability = (
            StorageContainerDataLoaderCapability(container_id)
        )
        container_data: Dict[str, Any] = CapabilityExecutor.execute(
            capability,
            self._request.context,
        )

        container_report: Dict[str, Any] = {
            "name": "container",
            "kind": "root",
            "children": [
                {
                    "name": "linkset",
                    "kind": "config",
                    "children": [],
                }
            ],
        }
        response_content: Dict[str, Any] = dict(container_data)
        response_content["tree"] = container_report

        return TreeCommandResponse(
            title="Container Inspection",
            description="Container data loaded successfully.",
            content=response_content,
        )


                # {
                #     "name": "datasets",
                #     "kind": "dir",
                #     "children": [
                #         {
                #             "name": "example.ttl",
                #             "kind": "file",
                #             "children": [],
                #         },
                #     ],
                # },
                # {
                #     "name": "ro-crate-metadata.json",
                #     "kind": "file",
                #     "children": [],
                # },
