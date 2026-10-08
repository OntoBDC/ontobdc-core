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

from ontobdc.annotation.plugin.machine.annotation_export_to_excel.etl import (
    AnnotationExportToExcelEtlEvent,
)
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelProcessStatePort,
    AnnotationExportToExcelStateTransitionHandlerPort,
)
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.state import (
    AnnotationExportToExcelProcessState,
)


class AnnotationExportToExcelStateTransitionHandler(
    AnnotationExportToExcelStateTransitionHandlerPort
):
    """
    Drive the annotation export to Excel statechart.

    Every state is an action of the current invocation: an export is made
    afresh each time it is asked for, so no state is observed as already
    reached, and each is validated by having been performed. Each state runs
    the capability declared for it and leaves its ETL file (see
    ``AnnotationExportToExcelEtlEvent``) with what the capability produced.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "AnnotationExportToExcelProcessStatePort"
    STATE_TO_CAPABILITY_ID: ClassVar[
        Dict[AnnotationExportToExcelProcessStatePort, str]
    ] = {
        AnnotationExportToExcelProcessState.EXPORT_SCOPE_IDENTIFIED: (
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "export_scope_identified"
        ),
        AnnotationExportToExcelProcessState.ANNOTATIONS_COLLECTED: (
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "annotations_collected"
        ),
        AnnotationExportToExcelProcessState.PHOTOS_COLLECTED: (
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "photos_collected"
        ),
        AnnotationExportToExcelProcessState.PHOTOS_DOWNSAMPLED: (
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "photos_downsampled"
        ),
        AnnotationExportToExcelProcessState.WORKBOOK_BUILT: (
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "workbook_built"
        ),
        AnnotationExportToExcelProcessState.WORKBOOK_SAVED: (
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "workbook_saved"
        ),
    }
    STATECHART_PACKAGE: ClassVar[str] = (
        "ontobdc.annotation.plugin.machine.annotation_export_to_excel"
    )
    STATECHART_FILE: ClassVar[str] = "standard_annotation_export_to_excel.yaml"
    FINAL_STATE: ClassVar[AnnotationExportToExcelProcessStatePort] = (
        AnnotationExportToExcelProcessState.WORKBOOK_SAVED
    )

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
        self._resolver: StrategyParamResolver = StrategyParamResolver(
            ResolverLoader(root_packages=capability_root_packages)
        )
        self._capability_loader: CapabilityLoader = CapabilityLoader(
            root_packages=capability_root_packages
        )
        self._active_state: AnnotationExportToExcelProcessStatePort = (
            AnnotationExportToExcelProcessState.UNDEFINED
        )
        self._last_performed_state: Optional[
            AnnotationExportToExcelProcessStatePort
        ] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> AnnotationExportToExcelProcessStatePort:
        return self._active_state

    def can_transit_to(self, to_state: AnnotationExportToExcelProcessStatePort) -> bool:
        return self._active_state != to_state

    def perform_state_transition(
        self,
        to_state: AnnotationExportToExcelProcessStatePort,
    ) -> None:
        capability: CapabilityPort = self._capability(to_state)
        self._logger.log_info(
            "Annotation export to Excel transition: "
            f"{self._active_state.value} -> {to_state.value}",
        )
        self._result = CapabilityExecutor.execute(
            capability,
            self._context,
            self._resolver,
        )
        AnnotationExportToExcelEtlEvent.write(
            AnnotationExportToExcelEtlEvent.container_of(self._context),
            to_state,
            self._result,
        )
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: AnnotationExportToExcelProcessStatePort,
        to_state: AnnotationExportToExcelProcessStatePort,
    ) -> bool:
        return from_state != to_state and self._last_performed_state == to_state

    def bind_active_state(self, state: AnnotationExportToExcelProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> Dict[str, Any]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=AnnotationExportToExcelProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self.statechart_file_path(),
        )
        try:
            worker.work()
        except CodeEvaluationError as error:
            # The statechart wraps whatever its actions raise; the caller
            # needs the error itself.
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise
        if self._last_performed_state != self.FINAL_STATE:
            reached: str = (
                self._last_performed_state.value
                if self._last_performed_state is not None
                else self._active_state.value
            )
            raise RuntimeError(
                f"Annotation export to Excel stopped at state '{reached}' "
                f"instead of '{self.FINAL_STATE.value}'."
            )
        return dict(self._result)

    @classmethod
    def statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(cls.STATECHART_PACKAGE, cls.STATECHART_FILE)

    @classmethod
    def state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(
            yaml.safe_load(cls.statechart_file_path().read_text(encoding="utf-8"))
        )

    def _capability(
        self,
        state: AnnotationExportToExcelProcessStatePort,
    ) -> CapabilityPort:
        capability_id: Optional[str] = self.STATE_TO_CAPABILITY_ID.get(state)
        if capability_id is None:
            raise ValueError(
                f"Annotation export to Excel capability not declared for state: {state.value}"
            )
        capability_type: Any = self._capability_loader.get(capability_id)
        if capability_type is None:
            raise ValueError(
                "Annotation export to Excel capability not found for state: "
                f"{state.value} (id: {capability_id})"
            )
        return capability_type()
