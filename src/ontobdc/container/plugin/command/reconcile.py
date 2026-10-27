from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.plugin.machine.file_reconciliation.machine import (
    FileReconciliationStateTransitionHandler,
)


class ContainerReconcileCommand(CliCommandPort):
    """
    Find the files the RO-Crate of a container states that are not on disk, and where a file of the
    same name is, find again by the hash of their content the ones that moved, and record what the files are now in the history the crate keeps: in each file's node and in the
    root dataset, where the files are named by an identifier. The files are not touched, and nothing
    the history had is taken out.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_reconcile",
        logical_component="container",
        description="Find the files the RO-Crate states that are not on disk and the files of the same name elsewhere, and record their current state in the history of the crate.",
        arguments=[
            {
                "accepts": ["--reconcile"],
                "description": "Reconcile the files the crate states with the files on disk.",
                "usage": "ontobdc container --reconcile [--container <id-or-path>]",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container, by storage identifier or filesystem "
                    "path. When omitted, it is resolved from the current "
                    "working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    RECONCILE_FLAG: ClassVar[str] = "--reconcile"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the reconciliation at the CLI routing stage.
        """
        if not args or args[0] != ContainerReconcileCommand.COMPONENT:
            return False

        return ContainerReconcileCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        result: Dict[str, Any] = FileReconciliationStateTransitionHandler(context).execute()
        missing: List[Dict[str, Any]] = result["missing"]
        return CommandResponse(
            title="File Reconciliation",
            description=(
                f"{len(missing)} files stated by the crate of «{container_path.name}» are not on disk; "
                f"{result['with_same_name']} of them have a file of the same name elsewhere and "
                f"{len(result['relocated'])} were found again by their content and "
                f"{len(result['relocated_by_name_and_size'])} by their name and size; "
                f"{result['recorded']} history entries were added to the files, "
                f"{result['identifiers_given']} files were given an identifier, "
                f"{result['dataset_entries_added']} entries were added to the history of the container."
            ),
            content={
                "missing": missing,
                "relocated": result["relocated"],
                "relocated_by_name_and_size": result["relocated_by_name_and_size"],
                "ambiguous": result["ambiguous"],
                "orphans": result["orphans"],
                "recorded": result["recorded"],
                "files_with_history": result["files_with_history"],
                "identifiers_given": result["identifiers_given"],
                "without_history": result["without_history"],
                "dataset_entries": result["dataset_entries"],
            },
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --reconcile with no value, and optionally --container
        with a value, in any order.
        """
        if ContainerReconcileCommand.RECONCILE_FLAG not in scoped_args:
            return False

        remaining: List[str] = [
            argument for argument in scoped_args if argument != ContainerReconcileCommand.RECONCILE_FLAG
        ]
        if len(remaining) not in (0, 2) or len(remaining) != len(scoped_args) - 1:
            return False
        if remaining and (remaining[0] != ContainerReconcileCommand.CONTAINER_FLAG or not remaining[1].strip() or remaining[1].startswith("--")):
            return False

        return True
