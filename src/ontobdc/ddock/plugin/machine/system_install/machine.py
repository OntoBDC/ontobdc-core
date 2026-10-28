from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import (
    CapabilityLoader,
    ResolverLoader,
)
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.adapter.system_lock import SystemLock
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.domain.model.system_install import ArchiveFiles, UnpackedPackage
from ontobdc.ddock.plugin.machine.system_install.port import (
    SystemInstallProcessStatePort,
    SystemInstallStateEvaluatorPort,
    SystemInstallStateTransitionHandlerPort,
)
from ontobdc.ddock.plugin.machine.system_install.state import (
    SystemInstallProcessState,
)
from ontobdc.ddock.plugin.machine.system_install.statechart import (
    SystemInstallStatechart,
)


class SystemInstallRequest:
    """
    The context keys the installation of a system reads and sets, and where
    it keeps what it downloads.

    The caller hands over where the container is and the address of the zip of
    ddock. What the installation downloads is unpacked into a work folder of
    the container, and stays there until the installation ends, so that an
    interrupted one can go on from what is already there.
    """

    CONTAINER_PATH_KEY: str = "ddock_container_path"
    DDOCK_ZIP_KEY: str = "ddock_install_zip"
    DDOCK_SOURCE_KEY: str = "ddock_install_source"
    BUILT_KEY: str = "ddock_node_built"
    WORK_FOLDER_NAME: str = ".ddock-install"

    @classmethod
    def container_path(cls, context: CliContextPort) -> Path:
        return Path(cls._text(context, cls.CONTAINER_PATH_KEY)).expanduser().resolve()

    @classmethod
    def ddock_zip(cls, context: CliContextPort) -> str:
        return cls._text(context, cls.DDOCK_ZIP_KEY)

    @classmethod
    def ddock_source(cls, context: CliContextPort) -> Optional[str]:
        """
        The address of the GitHub repository of ddock the install names, or
        nothing when it names none.
        """
        value: Any = context.get_parameter_value(cls.DDOCK_SOURCE_KEY)
        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()

    @classmethod
    def work_path(cls, context: CliContextPort) -> Path:
        return cls.container_path(context) / cls.WORK_FOLDER_NAME

    @classmethod
    def ddock_path(cls, context: CliContextPort) -> Path:
        return cls.work_path(context) / "ddock"

    @classmethod
    def package_path(cls, context: CliContextPort, index: int) -> Path:
        """
        Where the package at ``index`` of system.obdc is unpacked.
        """
        return cls.work_path(context) / "packages" / f"{index}"

    @classmethod
    def record_fetch(cls, folder: Path, archive: ArchiveFiles) -> None:
        """
        Note down which zip was unpacked into the folder, and the files of it
        that go into the container. It is written after the unpacking, so a
        folder that has it was unpacked entirely.
        """
        cls._record_path(folder).write_text(archive.model_dump_json(), encoding="utf-8")

    @classmethod
    def fetched(cls, folder: Path) -> Optional[ArchiveFiles]:
        """
        What was unpacked into the folder, or nothing when it was not
        unpacked, or not entirely.
        """
        record: Path = cls._record_path(folder)
        if not folder.is_dir() or not record.is_file():
            return None

        return ArchiveFiles.model_validate_json(record.read_text(encoding="utf-8"))

    @classmethod
    def discard_fetch(cls, folder: Path) -> None:
        """
        Remove what an earlier, interrupted unpacking left in the folder.
        """
        shutil.rmtree(folder, ignore_errors=True)
        cls._record_path(folder).unlink(missing_ok=True)

    @classmethod
    def packages(cls, context: CliContextPort, addresses: List[str]) -> List[UnpackedPackage]:
        """
        The packages among ``addresses`` that are unpacked in the work folder.
        """
        found: List[UnpackedPackage] = []
        index: int
        address: str
        for index, address in enumerate(addresses):
            folder: Path = cls.package_path(context, index)
            archive: Optional[ArchiveFiles] = cls.fetched(folder)
            if archive is not None:
                found.append(UnpackedPackage(address=address, path=folder, archive=archive))

        return found

    @staticmethod
    def _record_path(folder: Path) -> Path:
        return folder.parent / f"{folder.name}.json"

    @staticmethod
    def _text(context: CliContextPort, key: str) -> str:
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Required parameter is missing: {key}")

        return value.strip()


class SystemInstallStateEvaluatorAdapter(SystemInstallStateEvaluatorPort):
    """
    Reads what is on disk and reports how far the installation has got.

    Each state resolves its own capability and asks whether it already
    considers itself satisfied, in the order of the statechart. The
    installation is at the last state of the unbroken run of satisfied
    states, so a state that is satisfied is skipped. Building the node
    application is never satisfied: it runs every time.
    """

    def __init__(self) -> None:
        self._capability_loader: CapabilityLoader = CapabilityLoader()

    def evaluate(
        self,
        context: CliContextPort,
    ) -> SystemInstallProcessStatePort:
        reached_state: SystemInstallProcessStatePort = SystemInstallProcessState.UNDEFINED
        state_name: str
        for state_name in SystemInstallStatechart.sequence():
            state: SystemInstallProcessStatePort = SystemInstallProcessState.get_state(state_name)
            capability_type: Any = self._capability_loader.get(
                "org.ontobdc.ddock.plugin.capability.transformation.target."
                f"{state.value.strip('_')}"
            )
            if capability_type is None:
                raise ValueError(f"System install capability not found for state: {state.value}")

            is_satisfied: Any = getattr(capability_type(), "is_satisfied", None)
            try:
                satisfied: bool = callable(is_satisfied) and is_satisfied(context)
            except Exception:
                # What a state reads may not be there yet (no valid system.obdc);
                # the state itself then runs and reports the error.
                satisfied = False
            if not satisfied:
                return reached_state

            reached_state = state

        return reached_state


class SystemInstallStateTransitionHandler(SystemInstallStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        # Fails before anything runs when the container or the zip is not there.
        SystemInstallRequest.container_path(context)
        SystemInstallRequest.ddock_zip(context)

        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: SystemInstallStateEvaluatorPort = (
            SystemInstallStateEvaluatorAdapter()
        )
        self._active_state: Optional[SystemInstallProcessStatePort] = None
        self._observed_state: Optional[SystemInstallProcessStatePort] = None

    @property
    def current_state(self) -> SystemInstallProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> SystemInstallProcessStatePort:
        """
        The state the installation has reached, read once per machine step
        and held until something can have changed it.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: SystemInstallProcessStatePort) -> bool:
        active_state: SystemInstallProcessStatePort = self.current_state
        if active_state == SystemInstallProcessState.UNDEFINED:
            return to_state == SystemInstallProcessState.SYSTEM_DESCRIPTOR_VALID

        return active_state != to_state

    def perform_state_transition(
        self, to_state: SystemInstallProcessStatePort
    ) -> None:
        if self.observed_state == to_state:
            return

        self._logger.log_info(
            f"System install transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            "org.ontobdc.ddock.plugin.capability.transformation.target."
            f"{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"System install capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: SystemInstallProcessStatePort,
        to_state: SystemInstallProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        state_sequence: List[str] = SystemInstallStatechart.sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_sequence and observed_name != "undefined":
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the system "
                "install statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the system "
                "install statechart."
            )
        if observed_name == "undefined":
            return False

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def execute(self) -> CommandResponse:
        """
        Run the installation from the state the container is in to its last.
        What is downloaded is kept in a work folder of the container so that an
        installation that failed goes on from there. The folder is removed as
        soon as the container has everything it lists, whether or not the
        installation went on to the end.
        """
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=SystemInstallProcessState,
            state_context_name="SystemInstallProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=SystemInstallStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            # The statechart wraps whatever its actions raise; the caller
            # needs the error itself, such as a missing system.obdc.
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise
        finally:
            self._remove_work_folder_when_installed()

        return CommandResponse(
            title="System Installed",
            description="The system was installed in the container and its node application was compiled.",
            content={
                "container_path": str(SystemInstallRequest.container_path(self._context)),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _remove_work_folder_when_installed(self) -> None:
        """
        Remove the work folder once the container has all the files the lock
        lists: nothing in it is needed to go on from there.
        """
        container_path: Path = SystemInstallRequest.container_path(self._context)
        try:
            descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        except (FileNotFoundError, ValueError):
            return

        if SystemLock.installed(container_path, descriptor):
            shutil.rmtree(SystemInstallRequest.work_path(self._context), ignore_errors=True)

    def bind_active_state(self, state: SystemInstallProcessStatePort) -> None:
        self._active_state = state
