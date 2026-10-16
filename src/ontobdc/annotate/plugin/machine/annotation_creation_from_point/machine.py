from typing import Any, ClassVar, Dict, List, Optional, Tuple
from pathlib import Path

import yaml

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort

from ontobdc.annotate.plugin.machine.annotation_creation_from_point.etl import (
    AnnotationCreationFromPointEtlEvent,
)
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.port import (
    AnnotationCreationFromPointProcessStatePort,
    AnnotationCreationFromPointStateEvaluatorPort,
    AnnotationCreationFromPointStateTransitionHandlerPort,
)
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.state import (
    AnnotationCreationFromPointProcessState,
)


class AnnotationCreationFromPointStateEvaluatorAdapter(
    AnnotationCreationFromPointStateEvaluatorPort
):
    """
    Evaluate progress from the outputs the capabilities leave behind.

    Each state runs the capabilities declared for it, in order, resolved by
    id through a ``CapabilityLoader``. The packages the loader searches are
    given by whoever builds the machine, so a package that adds capabilities
    of its own (the drawing viewer, for instance) can have them run by the
    states they belong to. A capability that is a ``RootPackagesAwarePort``
    is told the same packages, for the plugins it discovers itself.

    The states that persist their results, ANNOTATION_TYPE_IDENTIFIED and
    FILE_METADATA_EXTRACTED, are observed through their capability's
    ``is_satisfied``. Loading the drawing, opening the viewer session,
    capturing the points on that same session, filling in the annotation details
    and creating the annotations
    at those points are actions of the current invocation: they are never
    observed as reached and are validated by having been performed.
    """

    STATE_TO_CAPABILITY_IDS: ClassVar[
        Dict[AnnotationCreationFromPointProcessStatePort, Tuple[str, ...]]
    ] = {
        AnnotationCreationFromPointProcessState.ANNOTATION_TYPE_IDENTIFIED: (
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "annotation_type_identified",
        ),
        AnnotationCreationFromPointProcessState.FILE_METADATA_EXTRACTED: (
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted",
        ),
        AnnotationCreationFromPointProcessState.DRAWABLE_DOCUMENTS_LOADED: (
            "org.ontobdc.annotate.plugin.capability.loader."
            "drawable_documents_loaded",
        ),
        AnnotationCreationFromPointProcessState.DRAWABLE_FILE_VIEWER_OPENED: (
            "org.ontobdc.annotate.plugin.capability.loader."
            "drawable_file_viewer_opened",
        ),
        AnnotationCreationFromPointProcessState.POINTS_CAPTURED: (
            "org.ontobdc.annotate.plugin.capability.loader.points_captured",
        ),
        AnnotationCreationFromPointProcessState.ANNOTATION_DETAILS_FILLED: (
            "org.ontobdc.annotate.plugin.capability.loader."
            "annotation_details_filled",
        ),
        AnnotationCreationFromPointProcessState.ANNOTATIONS_CREATED: (
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "annotations_created",
        ),
    }
    ACTION_STATES: ClassVar[
        Tuple[AnnotationCreationFromPointProcessStatePort, ...]
    ] = (
        AnnotationCreationFromPointProcessState.DRAWABLE_DOCUMENTS_LOADED,
        AnnotationCreationFromPointProcessState.DRAWABLE_FILE_VIEWER_OPENED,
        AnnotationCreationFromPointProcessState.POINTS_CAPTURED,
        AnnotationCreationFromPointProcessState.ANNOTATION_DETAILS_FILLED,
        AnnotationCreationFromPointProcessState.ANNOTATIONS_CREATED,
    )
    STATECHART_PACKAGE: ClassVar[str] = (
        "ontobdc.annotate.plugin.machine.annotation_creation_from_point"
    )
    STATECHART_FILE: ClassVar[str] = "standard_annotation_creation_from_point.yaml"

    def __init__(
        self,
        capability_root_packages: Tuple[str, ...] = (
            CapabilityLoader.DEFAULT_ROOT_PACKAGES
        ),
    ) -> None:
        self._capability_root_packages: Tuple[str, ...] = capability_root_packages
        self._capability_loader: CapabilityLoader = CapabilityLoader(
            root_packages=capability_root_packages
        )

    def evaluate(
        self,
        context: CliContextPort,
    ) -> AnnotationCreationFromPointProcessStatePort:
        reached_state: AnnotationCreationFromPointProcessStatePort = (
            AnnotationCreationFromPointProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self.state_sequence()[1:]:
            state: AnnotationCreationFromPointProcessStatePort = (
                AnnotationCreationFromPointProcessState.get_state(state_name)
            )
            if state in self.ACTION_STATES:
                return reached_state
            capability: CapabilityPort
            for capability in self.capabilities_for(state):
                if not capability.is_satisfied(context):
                    return reached_state
            reached_state = state
        return reached_state

    @classmethod
    def state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(cls._statechart_data())

    @classmethod
    def statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(cls.STATECHART_PACKAGE, cls.STATECHART_FILE)

    def capabilities_for(
        self,
        state: AnnotationCreationFromPointProcessStatePort,
    ) -> List[CapabilityPort]:
        if state not in self.STATE_TO_CAPABILITY_IDS:
            raise ValueError(
                "Annotation creation from point capability ids not declared "
                f"for state: {state.value}"
            )
        return [
            self._capability(state, capability_id)
            for capability_id in self.STATE_TO_CAPABILITY_IDS[state]
        ]

    def _capability(
        self,
        state: AnnotationCreationFromPointProcessStatePort,
        capability_id: str,
    ) -> CapabilityPort:
        capability_type: Any = self._capability_loader.get(capability_id)
        if capability_type is None:
            raise ValueError(
                "Annotation creation from point capability not found for "
                f"state: {state.value} (id: {capability_id})"
            )
        capability: CapabilityPort = capability_type()
        if isinstance(capability, RootPackagesAwarePort):
            capability.set_root_packages(self._capability_root_packages)
        return capability

    @classmethod
    def _statechart_data(cls) -> Dict[str, Any]:
        return yaml.safe_load(
            cls.statechart_file_path().read_text(encoding="utf-8")
        )


class AnnotationCreationFromPointStateTransitionHandler(
    AnnotationCreationFromPointStateTransitionHandlerPort
):
    """
    Drive the annotation creation from point statechart.

    Each state runs the capabilities declared for it, from the identification
    of the annotation type to the annotations created at the captured points,
    and every state leaves its ETL file (see
    ``AnnotationCreationFromPointEtlEvent``): with what its capabilities
    produced when this run performed it. A run resumes from the state
    already reached, so the states it starts past, which it does not
    perform, get their file too if they have none, with an empty result.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "AnnotationCreationFromPointProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
        capability_root_packages: Tuple[str, ...] = (
            CapabilityLoader.DEFAULT_ROOT_PACKAGES
        ),
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._capability_root_packages: Tuple[str, ...] = capability_root_packages
        self._resolver: StrategyParamResolver = StrategyParamResolver(
            ResolverLoader(root_packages=capability_root_packages)
        )
        self._state_evaluator: AnnotationCreationFromPointStateEvaluatorAdapter = (
            AnnotationCreationFromPointStateEvaluatorAdapter(
                capability_root_packages
            )
        )
        self._active_state: Optional[
            AnnotationCreationFromPointProcessStatePort
        ] = None
        self._observed_state: Optional[
            AnnotationCreationFromPointProcessStatePort
        ] = None
        self._last_performed_state: Optional[
            AnnotationCreationFromPointProcessStatePort
        ] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> AnnotationCreationFromPointProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> AnnotationCreationFromPointProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(
        self,
        to_state: AnnotationCreationFromPointProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: AnnotationCreationFromPointProcessStatePort,
    ) -> None:
        if to_state not in self._state_evaluator.ACTION_STATES and self._state_reaches(
            self.observed_state, to_state
        ):
            return

        capabilities: List[CapabilityPort] = self._state_evaluator.capabilities_for(
            to_state
        )
        self._logger.log_info(
            "Annotation creation from point transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        try:
            capability: CapabilityPort
            for capability in capabilities:
                self._result = CapabilityExecutor.execute(
                    capability,
                    self._context,
                    self._resolver,
                )
            self._write_etl_event(to_state, self._result)
            self._last_performed_state = to_state
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: AnnotationCreationFromPointProcessStatePort,
        to_state: AnnotationCreationFromPointProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        if to_state in self._state_evaluator.ACTION_STATES:
            return self._last_performed_state == to_state
        return self._state_reaches(self.observed_state, to_state)

    def bind_active_state(
        self,
        state: AnnotationCreationFromPointProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    def execute(self) -> Dict[str, Any]:
        self._write_missing_etl_events_up_to(self.observed_state)
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=AnnotationCreationFromPointProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self._state_evaluator.statechart_file_path(),
        )
        try:
            worker.work()
        except CodeEvaluationError as error:
            # The statechart wraps whatever its actions raise; the caller
            # needs the error itself, such as a capability nobody provides.
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise
        final_state: AnnotationCreationFromPointProcessStatePort = (
            AnnotationCreationFromPointProcessState.ANNOTATIONS_CREATED
        )
        # The final state is an action of this run, so it is the last state
        # performed rather than a state the evaluator can observe.
        if self._last_performed_state != final_state:
            reached: str = (
                self._last_performed_state.value
                if self._last_performed_state is not None
                else self.observed_state.value
            )
            raise RuntimeError(
                "Annotation creation from point stopped at state "
                f"'{reached}' instead of '{final_state.value}'."
            )
        return dict(self._result)

    def _state_reaches(
        self,
        observed_state: AnnotationCreationFromPointProcessStatePort,
        target_state: AnnotationCreationFromPointProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = self._state_evaluator.state_sequence()
        observed_name: str = observed_state.name.lower()
        target_name: str = target_state.name.lower()
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the statechart."
            )
        return state_sequence.index(observed_name) >= state_sequence.index(
            target_name
        )

    def _write_missing_etl_events_up_to(
        self,
        reached_state: AnnotationCreationFromPointProcessStatePort,
    ) -> None:
        container_path: Path = AnnotationCreationFromPointEtlEvent.container_of(
            self._context
        )
        state_name: str
        for state_name in self._state_evaluator.state_sequence()[1:]:
            state: AnnotationCreationFromPointProcessStatePort = (
                AnnotationCreationFromPointProcessState.get_state(state_name)
            )
            if not self._state_reaches(reached_state, state):
                return
            if not AnnotationCreationFromPointEtlEvent.path(container_path, state).is_file():
                AnnotationCreationFromPointEtlEvent.write(container_path, state, {})

    def _write_etl_event(
        self,
        state: AnnotationCreationFromPointProcessStatePort,
        result: Dict[str, Any],
    ) -> None:
        AnnotationCreationFromPointEtlEvent.write(
            AnnotationCreationFromPointEtlEvent.container_of(self._context),
            state,
            result,
        )

    def _forget_observed_state(self) -> None:
        self._observed_state = None
