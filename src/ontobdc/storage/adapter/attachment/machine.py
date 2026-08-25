from pathlib import Path
from typing import Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.storage.adapter.attachment.context import (
    AttachmentContextManager,
)
from ontobdc.storage.adapter.attachment.error import (
    AttachmentErrorClassifier,
)
from ontobdc.storage.adapter.attachment.plan import (
    AttachmentPlanConstants,
)
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)
from ontobdc.storage.domain.port.attach_machine import (
    ContainerAttachProcessStatePort,
    ContainerAttachStateEvaluatorPort,
    ContainerAttachStateTransitionHandlerPort,
)


_SUCCESS_STATES: List[ContainerAttachProcessState] = [
    ContainerAttachProcessState.UNDEFINED,
    ContainerAttachProcessState.CONTAINER_INSPECTED,
    ContainerAttachProcessState.IDENTITY_RESOLVED,
    ContainerAttachProcessState.CONTAINER_METADATA_ATTACHED,
    ContainerAttachProcessState.DATASETS_ATTACHED,
    ContainerAttachProcessState.STORAGE_INDEX_ATTACHED,
    ContainerAttachProcessState.CONTEXT_ATTACHED,
    ContainerAttachProcessState.CONTAINER_ATTACHED,
]

_CAPABILITY_ID_BY_STATE: Dict[ContainerAttachProcessState, str] = {
    ContainerAttachProcessState.CONTAINER_INSPECTED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_inspected"
    ),
    ContainerAttachProcessState.IDENTITY_RESOLVED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "identity_resolved"
    ),
    ContainerAttachProcessState.CONTAINER_METADATA_ATTACHED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_metadata_attached"
    ),
    ContainerAttachProcessState.DATASETS_ATTACHED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "datasets_attached"
    ),
    ContainerAttachProcessState.STORAGE_INDEX_ATTACHED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "storage_index_attached"
    ),
    ContainerAttachProcessState.CONTEXT_ATTACHED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "context_attached"
    ),
    ContainerAttachProcessState.CONTAINER_ATTACHED: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_attached"
    ),
}


def _capability_type_for_state(
    state: ContainerAttachProcessStatePort,
) -> Type[CapabilityPort]:
    try:
        capability_id = _CAPABILITY_ID_BY_STATE[
            ContainerAttachProcessState(state)
        ]
    except (KeyError, ValueError) as error:
        raise ValueError(
            f"No transformation capability is mapped to attach state: {state}"
        ) from error

    capability_type = CapabilityLoader().get(capability_id)
    if capability_type is None:
        raise ValueError(
            f"Container attach capability not found: {capability_id}"
        )
    return capability_type


class ContainerAttachStateEvaluatorAdapter(
    ContainerAttachStateEvaluatorPort
):
    """Infer the latest satisfied attachment state from its capabilities."""

    @property
    def process_state_class(self) -> Type[ContainerAttachProcessStatePort]:
        return ContainerAttachProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerAttachProcessStatePort:
        error_state_value = context.get_parameter_value(
            AttachmentPlanConstants.ATTACH_ERROR_PARAMETER
        )
        if isinstance(error_state_value, str) and error_state_value.strip():
            try:
                return ContainerAttachProcessState(error_state_value)
            except ValueError:
                pass

        for state in reversed(_SUCCESS_STATES):
            if state == ContainerAttachProcessState.UNDEFINED:
                continue
            capability_type = _capability_type_for_state(state)
            capability = capability_type()
            is_satisfied = getattr(capability, "is_satisfied", None)
            if not callable(is_satisfied):
                raise TypeError(
                    "Container attach state capability does not implement "
                    f"is_satisfied(context): {capability_type.__name__}"
                )
            if bool(is_satisfied(context)):
                return state

        return ContainerAttachProcessState.UNDEFINED


class ContainerAttachStateTransitionHandler(
    ContainerAttachStateTransitionHandlerPort
):
    """Execute the capability responsible for each attach target state."""

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: Optional[ContainerAttachStateEvaluatorPort] = None,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._target_path = Path(
            str(self._context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        self._state_evaluator = (
            state_evaluator or ContainerAttachStateEvaluatorAdapter()
        )
        self._logger = logger or NullLogRepository()
        self._active_state: Optional[ContainerAttachProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> ContainerAttachProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> ContainerAttachProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[ContainerAttachProcessStatePort]:
        return list(_SUCCESS_STATES)

    def can_transit_to(
        self,
        to_state: ContainerAttachProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: ContainerAttachProcessStatePort,
    ) -> None:
        self._logger.log_info(
            f"Container attach target state: {to_state.value}",
        )
        capability_type = _capability_type_for_state(to_state)
        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: ContainerAttachProcessStatePort,
        to_state: ContainerAttachProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        observed_state = self.observed_state
        if observed_state == to_state:
            return True
        if (
            to_state not in _SUCCESS_STATES
            or observed_state not in _SUCCESS_STATES
        ):
            return False
        return _SUCCESS_STATES.index(observed_state) > _SUCCESS_STATES.index(
            to_state
        )

    def execute(self) -> CommandResponse:
        visited_states: List[str] = []
        try:
            worker = StateWorkerAdapter(
                state_adapter=ContainerAttachProcessState,
                state_context_name="ContainerAttachProcessStatePort",
                handler=self,
                logger=self._logger,
                statechart_file_path=self._get_statechart_file_path(),
            )
            visited_states = worker.work()
            plan = self._context.get_parameter_value(
                AttachmentPlanConstants.ATTACH_PLAN_PARAMETER
            )
            content = {
                "container_path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            }
            if isinstance(plan, dict):
                content.update(
                    {
                        "source_container_id": plan.get(
                            "source_container_id"
                        ),
                        "container_id": plan.get("target_container_id"),
                        "datasets_attached": len(
                            plan.get("datasets") or []
                        ),
                    }
                )
            return CommandResponse(
                title="Storage Container Attached",
                description=(
                    "The imported container identity, datasets, storage index, "
                    "and execution context are attached to the current root."
                ),
                content=content,
            )
        except Exception as error:
            error_state = AttachmentErrorClassifier.error_state_for_exception(error)
            rollback_error: Optional[Exception] = None
            attachment_plan: object = self._context.get_parameter_value(
                AttachmentPlanConstants.ATTACH_PLAN_PARAMETER
            )
            if isinstance(attachment_plan, dict):
                try:
                    AttachmentContextManager(self._context).rollback_attachment()
                except Exception as caught_rollback_error:
                    rollback_error = caught_rollback_error
                    error_state = (
                        ContainerAttachProcessState.ATTACH_ROLLBACK_FAILED
                    )
            self._context.set_parameter_value(
                AttachmentPlanConstants.ATTACH_ERROR_PARAMETER,
                error_state.value,
            )
            self._active_state = error_state
            content = {
                "container_path": str(self._target_path),
                "current_state": error_state.value,
                "visited_states": visited_states,
                "error": str(error),
            }
            if rollback_error is not None:
                content["rollback_error"] = str(rollback_error)
            return ExceptionCommandResponse(
                title=error_state.label("en"),
                description=error_state.description("en"),
                content=content,
            )

    def _get_statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            __file__,
            "standard_container_attach.yaml",
        )

    def bind_active_state(
        self,
        state: ContainerAttachProcessStatePort,
    ) -> None:
        self._active_state = state
