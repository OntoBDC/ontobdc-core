from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import Capability, CapabilityExecutor
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import RunCommandResponse


class RunCapabilityCommand(CliCommandPort):
    """
    Execute a capability selected explicitly by its identifier.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="capability",
        logical_component="run",
        description="Execute a capability by its identifier.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--capability",
                ],
                "valued": True,
                "parameter": "capability_id",
                "description": (
                    "Canonical identifier of the capability to run, as "
                    "declared in its METADATA.id."
                ),
            },
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select which container the capability executes "
                    "against, either by its storage identifier or by a "
                    "filesystem path. When omitted, resolve the container "
                    "from the current working directory."
                ),
            },
        ],
    )

    CONTAINER_FLAG: ClassVar[str] = "--container"
    CAPABILITY_FLAG: ClassVar[str] = "--capability"

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the run command, with or without its optional container selector.
        """
        if not args or args[0] != "run":
            return False

        return RunCapabilityCommand._matches(args[1:])

    def check(self) -> bool:
        if not self._matches(self._request.command_args):
            return False

        target_capability: Any = self._request.context.get_parameter_value(
            "target_capability"
        )
        return isinstance(target_capability, Capability)

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --capability <id> with an
        optional --container <id-or-path>, in either order.

        The selector and the action are independent flags, not positions --
        which one a user writes first is not part of the command's meaning.
        """
        remaining: List[str] = list(scoped_args)
        capability_id: Optional[str] = RunCapabilityCommand._extract(
            remaining, RunCapabilityCommand.CAPABILITY_FLAG
        )
        if capability_id is None:
            return False

        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == RunCapabilityCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        """
        Remove and return the value following flag in remaining, or None
        when the flag is absent or has no value after it.
        """
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip():
            return None

        del remaining[index:index + 2]
        return value.strip()

    def run(self) -> RunCommandResponse:
        context: CliContextPort = self._request.context
        capability_id: str = str(
            context.get_parameter_value("capability_id") or ""
        ).strip()
        target_capability_value: Any = context.get_parameter_value(
            "target_capability"
        )
        if not isinstance(target_capability_value, Capability):
            raise ValueError("Target capability was not resolved.")

        result: Dict[str, Any] = CapabilityExecutor.execute(
            target_capability_value,
            context,
            StrategyParamResolver(ResolverLoader()),
        )

        return RunCommandResponse(
            title="OntoBDC Run",
            description="Capability executed successfully.",
            content={
                "capability_id": capability_id,
                "result": result,
            },
        )
