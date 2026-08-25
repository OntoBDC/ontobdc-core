from pathlib import Path
from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.storage.adapter.attachment.machine import (
    ContainerAttachStateTransitionHandler,
)
from ontobdc.storage.adapter.attachment.plan import (
    AttachmentPlanConstants,
)


class StorageAttachCommand(CliCommandPort):
    """Attach an imported storage container to the current project root."""

    METADATA = CliCommandMetadata(
        id="container_attach",
        logical_component="storage",
        description=(
            "Reconcile an imported container identity, datasets, storage index, "
            "and execution context with the current project root."
        ),
        arguments=[
            {
                "accepts": ["--container-path", "--container"],
                "valued": True,
                "description": (
                    "Filesystem path of the imported container to attach."
                ),
                "usage": (
                    "ontobdc storage --container-path <cp> --attach | "
                    "ontobdc storage --container <cp> --attach | "
                    "ontobdc storage --attach"
                ),
            },
            {
                "accepts": ["--attach"],
                "description": (
                    "Attach the imported container to the current local storage."
                ),
                "usage": (
                    "ontobdc storage --container-path <cp> --attach | "
                    "ontobdc storage --container <cp> --attach | "
                    "ontobdc storage --attach"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        path_flags: Tuple[str, ...] = ("--container-path", "--container")
        if not args or args[0] != "storage":
            return False
        rest: List[str] = args[1:]

        if not rest:
            return False

        if rest == ["--attach"]:
            return True

        for path_flag in path_flags:
            for attach_pos, token in enumerate(rest):
                if token != "--attach":
                    continue
                try:
                    pi: int = rest.index(path_flag)
                except ValueError:
                    continue
                if pi == attach_pos:
                    continue
                expected_val_pos: int = pi + 1
                if expected_val_pos == attach_pos:
                    continue
                if expected_val_pos >= len(rest):
                    continue
                raw_val: str = str(rest[expected_val_pos]).strip()
                if not raw_val or raw_val.startswith("--"):
                    continue
                total_flags: int = 0
                total_flags += 1  # attach flag
                total_flags += 1  # path flag
                total_tokens: int = total_flags + 1  # path value
                if len(rest) != total_tokens:
                    continue
                return True

        return False

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        command_args: List[str] = list(self._request.command_args)
        path_flags: Tuple[str, ...] = ("--container-path", "--container")
        raw_path: Optional[str] = None
        attach_flag_seen: bool = False
        i: int = 0
        total: int = len(command_args)
        while i < total:
            token: str = command_args[i]
            if token == "--attach":
                attach_flag_seen = True
                i += 1
                continue
            if token in path_flags:
                if i + 1 >= total:
                    return False
                candidate: str = str(command_args[i + 1]).strip()
                if not candidate:
                    return False
                if raw_path is not None:
                    return False
                raw_path = candidate
                i += 2
                continue
            return False

        if not attach_flag_seen:
            return False

        if raw_path is None:
            try:
                cwd_container: Path = Path.cwd()
                if cwd_container.is_dir():
                    raw_path = str(cwd_container)
            except (OSError, RuntimeError):
                raw_path = None

        if raw_path is None or not str(raw_path).strip():
            return False
        try:
            container_path: Path = Path(str(raw_path)).expanduser().resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            return False
        if not container_path.is_dir():
            return False

        context = self._request.context
        context.set_parameter_value("container_path", str(container_path))
        for parameter_name in (
            AttachmentPlanConstants.ATTACH_PLAN_PARAMETER,
            AttachmentPlanConstants.ATTACH_COMPLETED_PARAMETER,
            AttachmentPlanConstants.ATTACH_ERROR_PARAMETER,
        ):
            context.delete_parameter(parameter_name)
        return True

    def run(self) -> CommandResponse:
        handler = ContainerAttachStateTransitionHandler(
            context=self._request.context,
        )
        return handler.execute()
