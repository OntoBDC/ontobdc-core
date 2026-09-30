from __future__ import annotations

import yaml
from typing import Any, ClassVar, Dict, List, Optional
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.adapter.parameter import RequiredParameter

from ontobdc.context.plugin.machine.pdf_to_graph.port import (
    PdfToGraphProcessStatePort,
    PdfToGraphStateEvaluatorPort,
    PdfToGraphStateTransitionHandlerPort,
)
from ontobdc.context.plugin.machine.pdf_to_graph.state import (
    PdfToGraphProcessState,
)


class PdfToGraphStateEvaluatorAdapter(
    PdfToGraphStateEvaluatorPort
):
    """
    Reads the execution context and reports the state already reached by
    the PDF-to-knowledge-graph pipeline.

    The sequence walked is not a second, hand-typed copy of the
    statechart: it comes from the statechart YAML itself (its ``initial``
    state, then each state's own first declared transition target). Each
    state's capability is resolved by its explicit, per-state capability
    identifier using a ``CapabilityLoader`` lookup, never a hardcoded
    class reference. The YAML stays the only place this pipeline's
    sequence is declared.
    """

    STATE_TO_CAPABILITY_ID: ClassVar[
        Dict[PdfToGraphProcessStatePort, str]
    ] = {
        PdfToGraphProcessState.TEXT_READINESS_CHECKED: (
            "org.ontobdc.context.plugin.capability.transformation.target.text_readiness_checker"
        ),
        PdfToGraphProcessState.PDF_BLOCKS_EXTRACTED: (
            "org.ontobdc.context.plugin.capability.transformation.target.pdf_block_extraction"
        ),
    }

    def evaluate(
        self,
        context: CliContextPort,
    ) -> PdfToGraphProcessStatePort:
        """
        Return the state reached so far, walking the YAML's own sequence
        and stopping at the first state whose capability is missing or
        not yet satisfied.
        """
        reached_state: PdfToGraphProcessStatePort = (
            PdfToGraphProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self._state_sequence()[1:]:
            state: PdfToGraphProcessStatePort = (
                PdfToGraphProcessState.get_state(state_name)
            )
            capability: Optional[CapabilityPort] = self._capability_for(state)
            if capability is None or not capability.is_satisfied(context):
                return reached_state

            reached_state = state

        return reached_state

    @classmethod
    def _state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(cls._statechart_data())

    @staticmethod
    def _statechart_data() -> Dict[str, Any]:
        statechart_file_path: Path = StatechartLocator.locate(
            "ontobdc.context.plugin.machine.pdf_to_graph",
            "standard_pdf_to_graph.yaml",
        )

        return yaml.safe_load(
            statechart_file_path.read_text(encoding="utf-8")
        )

    @classmethod
    def _capability_for(
        cls,
        state: PdfToGraphProcessStatePort,
    ) -> Optional[CapabilityPort]:
        capability_id: Optional[str] = cls.STATE_TO_CAPABILITY_ID.get(state)
        if capability_id is None:
            return None
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            return None

        return capability_type()


class PdfToGraphStateTransitionHandler(
    PdfToGraphStateTransitionHandlerPort
):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: PdfToGraphStateEvaluatorPort = (
            PdfToGraphStateEvaluatorAdapter()
        )
        self._active_state: Optional[
            PdfToGraphProcessStatePort
        ] = None
        self._observed_state: Optional[
            PdfToGraphProcessStatePort
        ] = None

    @property
    def current_state(self) -> PdfToGraphProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> PdfToGraphProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(
        self,
        to_state: PdfToGraphProcessStatePort,
    ) -> bool:
        """
        Accept any target other than where the machine already is.

        The statechart is the single source of truth for which target a
        given state may transit to: sismic only ever calls this guard
        with the one target the current state's own YAML transition
        declares, so this handler does not re-declare that sequence.
        """
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: PdfToGraphProcessStatePort,
    ) -> None:
        observed_state: PdfToGraphProcessStatePort = (
            self.observed_state
        )
        if self._state_reaches(observed_state, to_state):
            return

        self._logger.log_info(
            "PDF-to-graph transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: Optional[str] = (
            PdfToGraphStateEvaluatorAdapter.STATE_TO_CAPABILITY_ID.get(
                to_state
            )
        )
        if capability_id is None:
            raise ValueError(
                "PDF-to-graph capability identifier not available for "
                f"state: {to_state.value}"
            )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(
                "PDF-to-graph capability not found: "
                f"{capability_id}"
            )

        capability: CapabilityPort = capability_type()

        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
                output_path=f"etl/context/training/file/{to_state.value}.json",
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: PdfToGraphProcessStatePort,
        to_state: PdfToGraphProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._state_reaches(self.observed_state, to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=PdfToGraphProcessState,
            state_context_name="PdfToGraphProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        source_raw: Any = self._context.get_parameter_value("source_path")

        summary: Dict[str, Any] = {
            "source_path": (
                str(Path(str(source_raw)).expanduser().resolve())
                if isinstance(source_raw, str) and source_raw.strip()
                else None
            ),
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }

        return CommandResponse(
            title="PDF-to-Graph Pipeline Completed",
            description=(
                "The PDF-to-knowledge-graph pipeline verified that the "
                "provided PDF contains enough extractable plain text, then "
                "extracted all positioned text blocks from every page using "
                "PyMuPDF."
            ),
            content=summary,
        )

    @staticmethod
    def _get_statechart_file_path() -> Path:
        return StatechartLocator.locate(
            "ontobdc.context.plugin.machine.pdf_to_graph",
            "standard_pdf_to_graph.yaml",
        )

    def bind_active_state(
        self,
        state: PdfToGraphProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    @staticmethod
    def _state_reaches(
        observed_state: PdfToGraphProcessStatePort,
        target_state: PdfToGraphProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = (
            PdfToGraphStateEvaluatorAdapter._state_sequence()
        )
        observed_name: str = observed_state.value.strip("_")
        target_name: str = target_state.value.strip("_")
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

    def _forget_observed_state(self) -> None:
        self._observed_state = None
