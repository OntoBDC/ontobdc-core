from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HealthCheckCommandResponse
from ontobdc.container.plugin.capability.health.container import (
    ContainerHealthCheckCapability,
)


class ContainerHealthCommand(CliCommandPort):
    """
    Command for reporting the health of a registered container.

    Health is what a container looks like against what it declares: the
    metadata it carries, the index that registers it, and the manifests
    that describe its files either agree or they do not.

    Which verifications say that is the health check capability's to know,
    not this command's: the command selects a container, asks the
    capability, and renders the listing it gets back. A verification added
    there shows up here with nothing to change.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_health",
        logical_component="container",
        description="Report the health of a registered container.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select which container to run health checks "
                    "against, by storage identifier or filesystem path. "
                    "When omitted, resolve the container from the "
                    "current working directory. Health compares what the "
                    "container declares in metadata, index and manifests "
                    "against the files it actually holds and reports "
                    "every verification that fails."
                ),
            },
        ],
    )

    HEALTH_FLAG: ClassVar[str] = "--health"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    HEALTHY_KEY: ClassVar[str] = "healthy"

    HEALTHY_DESCRIPTION: ClassVar[str] = "Every verification holds."
    UNHEALTHY_DESCRIPTION: ClassVar[str] = (
        "A verification did not hold. Run `ontobdc container --refresh` to "
        "bring the container back in line with the files it holds."
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container health command at the CLI routing stage.
        """
        if not args or args[0] != "container":
            return False

        return ContainerHealthCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        container_path: Any = self._request.context.get_parameter_value(
            "container_path"
        )

        return isinstance(container_path, str) and bool(container_path.strip())

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --health with an optional
        --container <id-or-path>, in either order.

        The selector and the action are independent flags, not positions --
        a user (or an automated caller filling in --container on their
        behalf) should be free to write either one first.
        """
        if ContainerHealthCommand.HEALTH_FLAG not in scoped_args:
            return False

        remaining: List[str] = list(scoped_args)
        remaining.remove(ContainerHealthCommand.HEALTH_FLAG)
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ContainerHealthCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> HealthCheckCommandResponse:
        """
        Report every verification the health check capability runs.
        """
        report: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerHealthCheckCapability(),
            self._request.context,
        )
        healthy: bool = bool(report.get(self.HEALTHY_KEY))

        return HealthCheckCommandResponse(
            title="Container Health",
            description=(
                self.HEALTHY_DESCRIPTION
                if healthy
                else self.UNHEALTHY_DESCRIPTION
            ),
            content=report,
            severity="SUCCESS" if healthy else "ERROR",
        )
