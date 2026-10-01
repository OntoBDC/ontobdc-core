from pathlib import Path
from typing import Any, List, Type
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateProcessStatePort,
    ContainerCreateStateEvaluatorPort,
)
from ontobdc.container.plugin.machine.container_create.machine import (
    ContainerCreateStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_create.state import (
    ContainerCreateProcessState,
)
from ontobdc.container.plugin.machine.container_create.statechart import (
    ContainerCreateStatechart,
)
from test.check.container.container_workspace import ContainerCheckWorkspace


class _FakeEvaluator(ContainerCreateStateEvaluatorPort):
    """Injectable evaluator for cache counts without touching disk."""

    def __init__(self, return_state: ContainerCreateProcessStatePort) -> None:
        self._return_state: ContainerCreateProcessStatePort = return_state
        self.evaluate_calls: int = 0

    def evaluate(self, context: CliContextPort) -> ContainerCreateProcessStatePort:
        self.evaluate_calls += 1
        return self._return_state


def _make_handler(
    workspace: ContainerCheckWorkspace,
    *,
    evaluator_state: ContainerCreateProcessStatePort = (
        ContainerCreateProcessState.DIRECTORY_READY
    ),
    logger: LogRepositoryPort = None,
) -> Any:
    context: CliContextPort = Mock(spec=CliContextPort)
    context.root_path = str(workspace.root_path)
    context.get_parameter_value.return_value = str(workspace.container_path)
    logger = logger if logger is not None else NullLogRepository()
    handler: ContainerCreateStateTransitionHandler = (
        ContainerCreateStateTransitionHandler(
            context=context,
            logger=logger,
        )
    )
    fake_evaluator: _FakeEvaluator = _FakeEvaluator(evaluator_state)
    object.__setattr__(handler, "_state_evaluator", fake_evaluator)
    return handler, context, fake_evaluator


class TestTransitionHandlerObservedStateCaching:
    """Read-once-per-step behavior for the on-disk state evaluator."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_observed_state_is_evaluated_once_then_cached(self) -> None:
        handler, _, evaluator = _make_handler(self.workspace)
        assert evaluator.evaluate_calls == 0

        first_read: ContainerCreateProcessStatePort = handler.observed_state
        assert evaluator.evaluate_calls == 1
        assert first_read is ContainerCreateProcessState.DIRECTORY_READY

        second_read: ContainerCreateProcessStatePort = handler.observed_state
        assert evaluator.evaluate_calls == 1
        assert second_read is first_read

    def test_forgetting_the_observation_forces_a_new_disk_read(self) -> None:
        handler, _, evaluator = _make_handler(self.workspace)
        handler.observed_state
        handler.observed_state
        assert evaluator.evaluate_calls == 1

        handler._forget_observed_state()
        third: ContainerCreateProcessStatePort = handler.observed_state
        assert evaluator.evaluate_calls == 2
        assert third is ContainerCreateProcessState.DIRECTORY_READY


class TestTransitionHandlerCurrentStateAndBindActiveState:
    """The active state override and its precedence over disk reading."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_current_state_reads_the_observed_disk_state_by_default(self) -> None:
        handler, _, evaluator = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.CONTAINER_METADATA_READY,
        )
        current: ContainerCreateProcessStatePort = handler.current_state
        assert evaluator.evaluate_calls == 1
        assert current is ContainerCreateProcessState.CONTAINER_METADATA_READY

    def test_bind_active_state_short_circuits_observed_state(self) -> None:
        handler, _, evaluator = _make_handler(self.workspace)
        handler.bind_active_state(
            ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED,
        )
        current: ContainerCreateProcessStatePort = handler.current_state
        assert evaluator.evaluate_calls == 0
        assert current is ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED

    def test_re_binding_active_state_overrides_the_previous_binding(self) -> None:
        handler, _, _ = _make_handler(self.workspace)
        handler.bind_active_state(ContainerCreateProcessState.DIRECTORY_READY)
        handler.bind_active_state(
            ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
        )
        assert handler.current_state is (
            ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY
        )


class TestTransitionHandlerCanTransitTo:
    """The two guarded rules from UNDEFINED and the != rule elsewhere."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_from_undefined_with_invalid_path_observed_allows_only_invalid_path(
        self,
    ) -> None:
        handler, _, evaluator = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.INVALID_PATH,
        )
        handler.bind_active_state(ContainerCreateProcessState.UNDEFINED)
        assert handler.current_state is ContainerCreateProcessState.UNDEFINED
        assert handler.can_transit_to(ContainerCreateProcessState.INVALID_PATH) is True
        assert handler.can_transit_to(ContainerCreateProcessState.DIRECTORY_READY) is False
        assert handler.can_transit_to(
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ) is False

    def test_from_undefined_without_invalid_path_allows_directory_ready_only(
        self,
    ) -> None:
        handler, _, evaluator = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.UNDEFINED,
        )
        handler.bind_active_state(ContainerCreateProcessState.UNDEFINED)
        assert handler.can_transit_to(ContainerCreateProcessState.DIRECTORY_READY) is True
        assert handler.can_transit_to(ContainerCreateProcessState.INVALID_PATH) is False
        assert handler.can_transit_to(
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ) is False

    def test_non_undefined_states_forbid_self_transitions_only(self) -> None:
        handler, _, evaluator = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.CONTAINER_METADATA_READY,
        )
        assert handler.can_transit_to(
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ) is False
        assert handler.can_transit_to(ContainerCreateProcessState.DIRECTORY_READY) is True
        assert handler.can_transit_to(
            ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED,
        ) is True

    def test_active_state_is_used_instead_of_observation_for_guards(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.UNDEFINED,
        )
        handler.bind_active_state(ContainerCreateProcessState.DIRECTORY_READY)
        assert handler.can_transit_to(ContainerCreateProcessState.DIRECTORY_READY) is False
        assert handler.can_transit_to(
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ) is True


class TestTransitionHandlerPerformStateTransition:
    """Capability loader/executor contract and the mandatory cache forget."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_noop_when_already_in_the_requested_state(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.CONTAINER_METADATA_READY,
        )
        with patch(
            "ontobdc.container.plugin.machine.container_create.machine.CapabilityLoader",
        ) as loader_class:
            handler.perform_state_transition(
                ContainerCreateProcessState.CONTAINER_METADATA_READY,
            )
            loader_class.assert_not_called()

    @pytest.mark.parametrize("state,expected_state_name", [
        (
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
            "container_metadata_ready",
        ),
        (
            ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
            "container_storage_index_ready",
        ),
        (
            ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED,
            "container_manifest_synced",
        ),
    ])
    def test_perform_state_transition_uses_the_named_capability(
        self,
        state: ContainerCreateProcessStatePort,
        expected_state_name: str,
    ) -> None:
        handler, context, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.DIRECTORY_READY,
        )
        expected_capability_id: str = (
            "org.ontobdc.container.plugin.capability.transformation.target."
            f"{expected_state_name}"
        )
        with patch(
            "ontobdc.container.plugin.machine.container_create.machine.CapabilityLoader",
        ) as loader_class, patch(
            "ontobdc.container.plugin.machine.container_create.machine.CapabilityExecutor",
        ) as executor_class, patch(
            "ontobdc.container.plugin.machine.container_create.machine.StrategyParamResolver",
        ) as resolver_class:
            loader_instance: Any = loader_class.return_value
            capability_type: Type[Any] = MagicMock()
            loader_instance.get.return_value = capability_type
            resolver_instance: Any = resolver_class.return_value
            handler.perform_state_transition(state)
            loader_instance.get.assert_called_once_with(expected_capability_id)
            capability_type.assert_called_once_with()
            resolver_class.assert_called_once()
            executor_class.execute.assert_called_once_with(
                capability_type.return_value,
                context,
                resolver_instance,
            )

    def test_missing_capability_raises_value_error_before_execution(self) -> None:
        handler, _, _ = _make_handler(self.workspace)
        with patch(
            "ontobdc.container.plugin.machine.container_create.machine.CapabilityLoader",
        ) as loader_class:
            loader_instance: Any = loader_class.return_value
            loader_instance.get.return_value = None
            with pytest.raises(ValueError, match="capability not found"):
                handler.perform_state_transition(
                    ContainerCreateProcessState.CONTAINER_METADATA_READY,
                )

    def test_observed_state_cache_is_cleared_even_when_capability_fails(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.DIRECTORY_READY,
        )
        _ = handler.observed_state
        with patch(
            "ontobdc.container.plugin.machine.container_create.machine.CapabilityLoader",
        ) as loader_class, patch(
            "ontobdc.container.plugin.machine.container_create.machine.CapabilityExecutor",
        ) as executor_class:
            loader_instance: Any = loader_class.return_value
            loader_instance.get.return_value = MagicMock()
            executor_class.execute.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError, match="boom"):
                handler.perform_state_transition(
                    ContainerCreateProcessState.CONTAINER_METADATA_READY,
                )
        assert handler._observed_state is None


class TestTransitionHandlerValidateStateTransition:
    """Forward/backward index validation against the statechart sequence."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_same_states_are_invalid_transitions(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.CONTAINER_METADATA_READY,
        )
        assert handler.validate_state_transition(
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ) is False

    def test_observed_state_outside_sequence_raises_value_error(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.INVALID_PATH,
        )
        with pytest.raises(ValueError, match="absent from"):
            handler.validate_state_transition(
                ContainerCreateProcessState.UNDEFINED,
                ContainerCreateProcessState.DIRECTORY_READY,
            )

    def test_target_state_outside_sequence_raises_value_error(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.DIRECTORY_READY,
        )
        with pytest.raises(ValueError, match="absent from"):
            handler.validate_state_transition(
                ContainerCreateProcessState.DIRECTORY_READY,
                ContainerCreateProcessState.UNDEFINED,
            )

    def test_observed_index_equal_to_or_after_target_is_allowed(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
        )
        assert handler.validate_state_transition(
            ContainerCreateProcessState.DIRECTORY_READY,
            ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
        ) is True
        assert handler.validate_state_transition(
            ContainerCreateProcessState.DIRECTORY_READY,
            ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ) is True
        assert handler.validate_state_transition(
            ContainerCreateProcessState.DIRECTORY_READY,
            ContainerCreateProcessState.DIRECTORY_READY,
        ) is False

    def test_target_further_ahead_than_observation_is_rejected(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.DIRECTORY_READY,
        )
        assert handler.validate_state_transition(
            ContainerCreateProcessState.DIRECTORY_READY,
            ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED,
        ) is False


class TestTransitionHandlerExecuteAndFinalResponse:
    """Worker delegation and the two CommandResponse branches."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_execute_delegates_to_the_state_worker_and_returns_success_response(
        self,
    ) -> None:
        visited: List[str] = [
            ContainerCreateProcessState.DIRECTORY_READY.value,
            ContainerCreateProcessState.CONTAINER_METADATA_READY.value,
            ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY.value,
        ]
        handler, context, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
        )
        with patch(
            "ontobdc.container.plugin.machine.container_create.machine.StateWorkerAdapter",
        ) as worker_class:
            worker_instance: Any = worker_class.return_value
            worker_instance.work.return_value = list(visited)
            response: CommandResponse = handler.execute()
            worker_class.assert_called_once_with(
                state_adapter=ContainerCreateProcessState,
                state_context_name="ContainerCreateProcessStatePort",
                handler=handler,
                logger=handler._logger,
                statechart_file_path=ContainerCreateStatechart.path(),
            )
            worker_instance.work.assert_called_once_with()
        assert isinstance(response, CommandResponse)
        assert not isinstance(response, ExceptionCommandResponse)
        assert response.content["path"] == str(self.workspace.container_path)
        assert response.content["current_state"] == (
            ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY.value
        )
        assert response.content["visited_states"] == visited
        assert response.content["exists"] is True

    def test_build_final_response_wraps_invalid_path_into_exception_response(
        self,
    ) -> None:
        import shutil
        shutil.rmtree(self.workspace.container_path)
        invalid_file: Path = self.workspace.root_path / "invalid"
        invalid_file.write_text("x", encoding="utf-8")
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerCreateProcessState.INVALID_PATH,
        )
        object.__setattr__(
            handler, "_target_path", invalid_file,
        )
        visited: List[str] = [ContainerCreateProcessState.INVALID_PATH.value]
        response: CommandResponse = handler._build_final_response(visited)
        assert isinstance(response, ExceptionCommandResponse)
        assert response.content["path"] == str(invalid_file)
        assert response.content["current_state"] == (
            ContainerCreateProcessState.INVALID_PATH.value
        )
        assert response.content["visited_states"] == visited
        assert "exists" not in response.content
