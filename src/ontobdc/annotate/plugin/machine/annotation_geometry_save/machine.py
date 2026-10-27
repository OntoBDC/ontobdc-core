from typing import ClassVar, Optional, Set, Tuple, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from ontobdc.annotate.plugin.machine.annotation_geometry_save.port import (
    AnnotationGeometrySaveProcessStatePort,
    AnnotationGeometrySaveRequestPort,
    AnnotationGeometrySaveStateTransitionHandlerPort,
)
from ontobdc.annotate.plugin.machine.annotation_geometry_save.state import AnnotationGeometrySaveProcessState


class AnnotationGeometrySaveStateTransitionHandler(AnnotationGeometrySaveStateTransitionHandlerPort):
    """
    Drives the saving of a shape on an annotation.

    The machine always starts from the beginning and a state is reached only by having just performed it. Each
    state's capability is resolved by id through the CapabilityLoader, never imported concretely.
    """

    CAPABILITY_ID_PREFIX: ClassVar[str] = (
        "org.ontobdc.annotate.plugin.capability.transformation.target."
    )
    CAPABILITY_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = CapabilityLoader.DEFAULT_ROOT_PACKAGES
    STATECHART_PACKAGE: ClassVar[str] = "ontobdc.annotate.plugin.machine.annotation_geometry_save"
    STATECHART_FILE: ClassVar[str] = "standard_annotation_geometry_save.yaml"
    STATE_CONTEXT_NAME: ClassVar[str] = "AnnotationGeometrySaveProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._active_state: AnnotationGeometrySaveProcessStatePort = AnnotationGeometrySaveProcessState.UNDEFINED
        self._performed: Set[AnnotationGeometrySaveProcessStatePort] = set()

    @property
    def current_state(self) -> AnnotationGeometrySaveProcessStatePort:
        return self._active_state

    def can_transit_to(self, to_state: AnnotationGeometrySaveProcessStatePort) -> bool:
        return to_state not in self._performed

    def perform_state_transition(self, to_state: AnnotationGeometrySaveProcessStatePort) -> None:
        self._logger.log_info(
            f"Annotation geometry save transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{to_state.value.strip('_')}"
        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=self.CAPABILITY_ROOT_PACKAGES
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"Annotation geometry save capability not found for state: "
                f"{to_state.value} (id: {capability_id})"
            )

        CapabilityExecutor.execute(capability_type(), self._context)
        self._performed.add(to_state)

    def validate_state_transition(
        self,
        from_state: AnnotationGeometrySaveProcessStatePort,
        to_state: AnnotationGeometrySaveProcessStatePort,
    ) -> bool:
        return from_state != to_state and to_state in self._performed

    def bind_active_state(self, state: AnnotationGeometrySaveProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=AnnotationGeometrySaveProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=StatechartLocator.locate(
                self.STATECHART_PACKAGE,
                self.STATECHART_FILE,
            ),
        )
        worker.work()

        saved: int = int(self._context.get_parameter_value(AnnotationGeometrySaveRequestPort.SAVED_KEY) or 0)
        guid: str = str(self._context.get_parameter_value(AnnotationGeometrySaveRequestPort.GUID_KEY))

        return CommandResponse(
            title="Annotation Geometry Saved",
            description=f"Changed {saved} geometries of the annotation {guid}.",
            content={
                "global_id": guid,
                "operation": self._context.get_parameter_value(AnnotationGeometrySaveRequestPort.OPERATION_KEY),
                "changed": saved,
                "geometries": self._context.get_parameter_value(AnnotationGeometrySaveRequestPort.GEOMETRIES_KEY),
            },
        )
