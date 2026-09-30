from typing import Any, ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import ExceptionCommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException


class AnnotateCommand(CliCommandPort):
    """
    Command for annotating a file held by a selected container.

    Routing and selector resolution are in place: the container and the file
    are declared here and resolved by the parameter stage before ``check``
    runs, so this command never reaches for a selector strategy itself. The
    annotation pipeline has not been restored yet, so ``run`` reports that
    instead of annotating anything.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate",
        logical_component="annotate",
        description="Annotate a file held by a selected container.",
        arguments=[
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that holds the file to "
                    "annotate, by storage identifier or filesystem "
                    "path."
                ),
            },
            {
                "accepts": [
                    "--file",
                ],
                "valued": True,
                "parameter": "file",
                "description": (
                    "Select the file target of the annotation step, by "
                    "its global identifier or its filesystem path "
                    "inside the container."
                ),
            },
        ],
    )

    CONTAINER_FLAG: ClassVar[str] = "--container"
    FILE_FLAG: ClassVar[str] = "--file"

    # Kept short on purpose: the widget adapter renders this value inside a
    # fenced block, which the terminal surface prints verbatim, without
    # wrapping it to the frame width.
    _PENDING_ERROR: ClassVar[str] = "Annotation pipeline not restored."
    _PENDING_REASON: ClassVar[str] = (
        "Annotating a file is not available in this build: the annotation "
        "pipeline has not been restored yet."
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotate command at the CLI routing stage.
        """
        if not args or args[0] != "annotate":
            return False

        return AnnotateCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._values(self._request.command_args) is not None

    @staticmethod
    def _values(scoped_args: List[str]) -> Optional[Tuple[str, str]]:
        """
        Return the (container, file) pair these scoped args name, with
        --container and --file in either order, or None when they do not
        name one.

        Both flags are required -- but which one a user writes first is
        not part of the command's meaning.
        """
        remaining: List[str] = list(scoped_args)
        container: Optional[str] = AnnotateCommand._extract(
            remaining, AnnotateCommand.CONTAINER_FLAG
        )
        file_value: Optional[str] = AnnotateCommand._extract(
            remaining, AnnotateCommand.FILE_FLAG
        )
        if container is None or file_value is None or remaining:
            return None

        return container, file_value

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

    def run(self) -> ExceptionCommandResponse:
        """
        Report that the annotation pipeline is not available yet.
        """
        container_id: str = self._resolved_parameter("container_id")

        return ExceptionCommandResponse(
            title="Annotation Not Available",
            description=self._PENDING_REASON,
            content={
                "error": self._PENDING_ERROR,
                "container_id": container_id,
                "file_id": self._request.context.get_parameter_value("file_id"),
                "file_path": self._request.context.get_parameter_value("file_path"),
            },
        )

    def _resolved_parameter(self, name: str) -> str:
        """
        Return the value the parameter stage resolved under the given name.
        """
        value: Any = self._request.context.get_parameter_value(name)
        if not isinstance(value, str) or not value.strip():
            raise CliCommandArgumentException(
                f"Required parameter is missing: {name}"
            )

        return value.strip()
