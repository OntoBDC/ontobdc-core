from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as hotfix_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as hotfix_container_storage_index_ready,
)
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshStateTransitionHandlerPort,
)


class ContainerAttachCommand(CliCommandPort, LoggerAwarePort):
    """
    Attach an imported container onto the current storage root.

    A container that already carries its metadata — and its datasets — from
    another machine simply needs two things to be usable locally: its
    metadata has to be valid on disk (it may be stale by the current
    machine's expectations around location/semantic fields), and the storage
    index has to know about it. Attaching does those two things: it
    enforces container metadata readiness, then it writes the container
    entry into the storage index, and finally it runs the refresh pipeline
    on top so datasets, datapackage, manifest and RO-Crate are reconciled
    with what the container actually holds.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_attach",
        logical_component="container",
        description=(
            "Attach an existing imported container onto the current storage "
            "root."
        ),
        arguments=[
            {
                "accepts": [
                    "--container-path",
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Filesystem path of the imported container to "
                    "attach. When omitted, attach uses the current working "
                    "directory as the target container."
                ),
            },
            {
                "accepts": ["--attach"],
                "description": (
                    "Validate container metadata, register the container "
                    "in the root storage index and then run the refresh "
                    "pipeline so datasets, manifests and RO-Crate agree "
                    "with what the container actually holds."
                ),
            },
        ],
    )

    ATTACH_FLAG: ClassVar[str] = "--attach"
    CONTAINER_PATH_FLAGS: ClassVar[tuple] = (
        "--container-path",
        "--container",
    )
    COMPONENT: ClassVar[str] = "container"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container attach command at the CLI routing stage.
        """
        if not args or args[0] != ContainerAttachCommand.COMPONENT:
            return False

        rest: List[str] = list(args[1:])
        if rest == [ContainerAttachCommand.ATTACH_FLAG]:
            return True

        attach_seen: bool = False
        path_flag_seen: bool = False
        path_value_seen: bool = False
        idx: int = 0
        total: int = len(rest)
        while idx < total:
            token: str = rest[idx]
            if token == ContainerAttachCommand.ATTACH_FLAG:
                if attach_seen:
                    return False
                attach_seen = True
                idx += 1
                continue
            if token in ContainerAttachCommand.CONTAINER_PATH_FLAGS:
                if path_flag_seen:
                    return False
                if idx + 1 >= total:
                    return False
                next_token: str = str(rest[idx + 1]).strip()
                if not next_token or next_token.startswith("--"):
                    return False
                path_flag_seen = True
                path_value_seen = True
                idx += 2
                continue
            return False

        if not attach_seen:
            return False
        expected_tokens: int = 0
        expected_tokens += 1 if attach_seen else 0
        expected_tokens += 1 if path_flag_seen else 0
        expected_tokens += 1 if path_value_seen else 0
        if expected_tokens != total:
            return False
        return True

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        """
        Validate the attach arguments and resolve the target container path.
        """
        command_args: List[str] = list(self._request.command_args)
        attach_flag_seen: bool = False
        raw_container_path: Any = None
        idx: int = 0
        total: int = len(command_args)
        while idx < total:
            token: str = command_args[idx]
            if token == self.ATTACH_FLAG:
                if attach_flag_seen:
                    return False
                attach_flag_seen = True
                idx += 1
                continue
            if token in self.CONTAINER_PATH_FLAGS:
                if idx + 1 >= total:
                    return False
                candidate: Any = command_args[idx + 1]
                if not isinstance(candidate, str) or not candidate.strip():
                    return False
                if raw_container_path is not None:
                    return False
                raw_container_path = candidate.strip()
                idx += 2
                continue
            return False

        if not attach_flag_seen:
            return False

        if raw_container_path is None:
            try:
                cwd: Path = Path.cwd()
                if cwd.is_dir():
                    raw_container_path = str(cwd)
            except (OSError, RuntimeError):
                raw_container_path = None

        if not isinstance(raw_container_path, str) or not raw_container_path.strip():
            return False
        try:
            container_path: Path = Path(raw_container_path).expanduser().resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            return False
        if not container_path.is_dir():
            return False

        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value(
            "container_path",
            str(container_path),
        )
        return True

    def run(self) -> CommandResponse:
        """
        Make the container valid locally: metadata, index, refresh.
        """
        container_path_raw: Any = self._request.context.get_parameter_value(
            "container_path"
        )
        root_path_raw: Any = str(self._request.context.root_path).strip()
        if not isinstance(container_path_raw, str) or not container_path_raw.strip():
            raise ValueError(
                "ContainerAttachCommand.run requires a container_path in "
                "the context."
            )
        container_path_str: str = container_path_raw.strip()
        root_path_str: str = root_path_raw

        self._ensure_metadata_ready(
            container_path=container_path_str,
            root_path=root_path_str,
        )
        self._ensure_storage_index_ready(
            container_path=container_path_str,
            root_path=root_path_str,
        )

        handler: ContainerRefreshStateTransitionHandlerPort = (
            ContainerRefreshStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )
        refresh_response: CommandResponse = handler.execute()

        title: str = "Storage Container Attached"
        try:
            content: Dict[str, Any] = dict(refresh_response.content or {})
        except Exception:
            content = {}
        content["container_path"] = container_path_str
        description: str = (
            "Container metadata and storage index entry reconciled; "
            + str(refresh_response.description or "")
        )

        return CommandResponse(
            title=title,
            description=description,
            content=content,
            severity=refresh_response.severity,
        )

    @staticmethod
    def _ensure_metadata_ready(
        *,
        container_path: str,
        root_path: str,
    ) -> None:
        if check_container_metadata_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_metadata_ready(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to make container metadata valid while "
                    "attaching the container."
                )
        if check_container_metadata_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container metadata is still invalid after the attach hotfix."
            )

    @staticmethod
    def _ensure_storage_index_ready(
        *,
        container_path: str,
        root_path: str,
    ) -> None:
        if check_container_storage_index_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_storage_index_ready(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to write the container storage index entry "
                    "while attaching the container."
                )
        if check_container_storage_index_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container storage index entry is still invalid after the "
                "attach hotfix."
            )
