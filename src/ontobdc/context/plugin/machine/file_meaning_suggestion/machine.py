from __future__ import annotations

import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.cli.domain.response.command import (
    InteractiveCommandResponse,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.context.plugin.machine.file_meaning_suggestion.port import (
    FileMeaningSuggestionProcessStatePort,
    FileMeaningSuggestionStateEvaluatorPort,
    FileMeaningSuggestionStateTransitionHandlerPort,
)
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import (
    FileMeaningSuggestionProcessState,
)
from ontobdc.context.adapter.suggestion_tree import (
    SuggestionStructuredData,
    SuggestionTreeBuilder,
)
from ontobdc.context.adapter.suggestion_textual import (
    SuggestionApprovalAdapter,
    SuggestionApprovalResult,
)


class FileMeaningSuggestionStateEvaluatorAdapter(
    FileMeaningSuggestionStateEvaluatorPort
):
    """
    Reads the container's ETL event files on disk and reports the state
    already reached.

    The sequence walked is not a second, hand-typed copy of the
    statechart: it comes from the statechart YAML itself (its
    ``initial`` state, then each state's own first declared transition
    target), and each state's capability is resolved the same way
    ``perform_state_transition`` already resolves one -- a
    ``CapabilityLoader`` lookup on the state's own conventional
    capability id, never a hardcoded class reference. The YAML stays the
    only place this pipeline's sequence is declared.
    """

    def evaluate(
        self,
        context: CliContextPort,
    ) -> FileMeaningSuggestionProcessStatePort:
        """
        Return the state reached so far, walking the YAML's own sequence
        and stopping at the first state whose capability is missing or
        not yet satisfied.
        """
        reached_state: FileMeaningSuggestionProcessStatePort = (
            FileMeaningSuggestionProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self._state_sequence()[1:]:
            state: FileMeaningSuggestionProcessStatePort = (
                FileMeaningSuggestionProcessState.get_state(state_name)
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
            "ontobdc.context.plugin.machine.file_meaning_suggestion",
            "standard_file_meaning_suggestion.yaml",
        )

        return yaml.safe_load(
            statechart_file_path.read_text(encoding="utf-8")
        )

    @staticmethod
    def _capability_for(
        state: FileMeaningSuggestionProcessStatePort,
    ) -> Optional[CapabilityPort]:
        capability_id: str = (
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            f"{state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            return None

        return capability_type()


class FileMeaningSuggestionStateTransitionHandler(
    FileMeaningSuggestionStateTransitionHandlerPort
):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: FileMeaningSuggestionStateEvaluatorPort = (
            FileMeaningSuggestionStateEvaluatorAdapter()
        )
        self._active_state: Optional[
            FileMeaningSuggestionProcessStatePort
        ] = None
        self._observed_state: Optional[
            FileMeaningSuggestionProcessStatePort
        ] = None

    @property
    def current_state(self) -> FileMeaningSuggestionProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> FileMeaningSuggestionProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(
        self,
        to_state: FileMeaningSuggestionProcessStatePort,
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
        to_state: FileMeaningSuggestionProcessStatePort,
    ) -> None:
        observed_state: FileMeaningSuggestionProcessStatePort = (
            self.observed_state
        )
        if self._state_reaches(observed_state, to_state):
            return

        self._logger.log_info(
            "File meaning suggestion transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            f"{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(
                "File meaning suggestion capability not found: "
                f"{capability_id}"
            )

        capability: CapabilityPort = capability_type()

        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: FileMeaningSuggestionProcessStatePort,
        to_state: FileMeaningSuggestionProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._state_reaches(self.observed_state, to_state)

    def execute(self) -> InteractiveCommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=FileMeaningSuggestionProcessState,
            state_context_name="FileMeaningSuggestionProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        container_raw: Any = self._context.get_parameter_value("container_path")
        container_path: Path = (
            Path(str(container_raw)).expanduser().resolve()
            if isinstance(container_raw, str) and container_raw.strip()
            else Path.cwd()
        )
        tree: Dict[str, Any] = SuggestionTreeBuilder.of(
            container_path=container_path
        )
        structured: SuggestionStructuredData = (
            SuggestionTreeBuilder.export_structured(
                container_path=container_path
            )
        )
        summary: Dict[str, Any] = {
            "container_path": str(container_path),
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        approval_result: Optional[SuggestionApprovalResult] = (
            SuggestionApprovalAdapter().open(structured)
        )
        content: Dict[str, Any] = {
            "tree": tree,
            "summary": summary,
            "structured_categories_count": len(structured.categories),
            "structured_unmatched_count": len(structured.unmatched_files),
        }
        if approval_result is not None:
            approved_cats: List[str] = list(approval_result.selected_categories)
            approved_by_cat: Dict[str, List[str]] = {}
            for (iri, fpaths) in approval_result.selected_files_by_category:
                approved_by_cat[iri] = list(fpaths)
            content["approval"] = {
                "approved": True,
                "selected_categories": approved_cats,
                "selected_files_by_category": approved_by_cat,
            }
            description_suffix: str = (
                f" User approved {len(approved_cats)} category(ies) with "
                f"{sum(len(v) for v in approved_by_cat.values())} file selection(s)."
            )
        else:
            content["approval"] = {"approved": False}
            description_suffix: str = " User cancelled the interactive approval."
        return InteractiveCommandResponse(
            title="File Meaning Suggestion Completed",
            description=(
                "The file meaning suggestion process normalized each path, "
                "identified its language, extracted file metadata, "
                "lemmatized the path, computed token statistics, "
                "extracted statistically supported chunks, matched them "
                "against ontology term labels (exact = 1.0 first; fuzzy "
                "substring min(len)/max(len) as fallback; unmatched 0), "
                "and aggregated the results by ontology category with "
                "per-file best score painted by magnitude."
                + description_suffix
            ),
            content=content,
        )

    @staticmethod
    def _get_statechart_file_path() -> Path:
        return StatechartLocator.locate(
            "ontobdc.context.plugin.machine.file_meaning_suggestion",
            "standard_file_meaning_suggestion.yaml",
        )

    def bind_active_state(
        self,
        state: FileMeaningSuggestionProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    @staticmethod
    def _state_reaches(
        observed_state: FileMeaningSuggestionProcessStatePort,
        target_state: FileMeaningSuggestionProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = (
            FileMeaningSuggestionStateEvaluatorAdapter._state_sequence()
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
