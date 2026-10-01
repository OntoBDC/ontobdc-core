from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshProcessStatePort,
    ContainerRefreshStateEvaluatorPort,
)
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_refresh.state import (
    ContainerRefreshProcessState,
)
from ontobdc.container.plugin.capability.transformation.container_cleaned import (
    ContainerCleanedCapability,
)
from test.check.container.container_workspace import ContainerCheckWorkspace


class _FakeEvaluator(ContainerRefreshStateEvaluatorPort):
    """Injectable evaluator returning a fixed state per call."""

    def __init__(self, return_state: ContainerRefreshProcessStatePort) -> None:
        self._return_state: ContainerRefreshProcessStatePort = return_state
        self.evaluate_calls: int = 0

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerRefreshProcessStatePort:
        self.evaluate_calls += 1
        return self._return_state


def _make_handler(
    workspace: ContainerCheckWorkspace,
    *,
    evaluator_state: ContainerRefreshProcessStatePort = (
        ContainerRefreshProcessState.UNDEFINED
    ),
    logger: LogRepositoryPort = None,
    cleanup_capability: ContainerCleanedCapability = None,
) -> Any:
    context: CliContextPort = Mock(spec=CliContextPort)
    context.root_path = str(workspace.root_path)
    context.get_parameter_value.side_effect = lambda key: (
        "container-xyz"
        if key == "container_id"
        else str(workspace.container_path)
    )
    logger = logger if logger is not None else NullLogRepository()
    cleanup = cleanup_capability or ContainerCleanedCapability()
    handler: ContainerRefreshStateTransitionHandler = (
        ContainerRefreshStateTransitionHandler(
            context=context,
            logger=logger,
            cleanup_capability=cleanup,
        )
    )
    fake_evaluator: _FakeEvaluator = _FakeEvaluator(evaluator_state)
    object.__setattr__(handler, "_state_evaluator", fake_evaluator)
    return handler, context, fake_evaluator


class TestRefreshTransitionHandlerObservedStateEvaluations:
    """Evaluator is invoked on every observed_state access (no cache)."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_observed_state_invokes_evaluator_each_access(self) -> None:
        handler, _, evaluator = _make_handler(self.workspace)
        assert evaluator.evaluate_calls == 0

        first: ContainerRefreshProcessStatePort = handler.observed_state
        assert evaluator.evaluate_calls == 1
        assert first is ContainerRefreshProcessState.UNDEFINED

        second: ContainerRefreshProcessStatePort = handler.observed_state
        assert evaluator.evaluate_calls == 2
        assert second is first

    def test_current_state_uses_observed_when_no_active_state_bound(
        self,
    ) -> None:
        handler, _, evaluator = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
        )
        current: ContainerRefreshProcessStatePort = handler.current_state
        assert evaluator.evaluate_calls == 1
        assert current is ContainerRefreshProcessState.CONTAINER_HEALTHY


class TestRefreshTransitionHandlerBindActiveState:
    """Active state short-circuits evaluator reading."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_bind_active_state_short_circuits_observed_state(self) -> None:
        handler, _, evaluator = _make_handler(self.workspace)
        handler.bind_active_state(
            ContainerRefreshProcessState.CONTAINER_UPDATED,
        )
        current: ContainerRefreshProcessStatePort = handler.current_state
        assert evaluator.evaluate_calls == 0
        assert current is ContainerRefreshProcessState.CONTAINER_UPDATED

    def test_re_binding_active_state_overrides_previous_value(self) -> None:
        handler, _, _ = _make_handler(self.workspace)
        handler.bind_active_state(ContainerRefreshProcessState.CONTAINER_HEALTHY)
        handler.bind_active_state(
            ContainerRefreshProcessState.CONTAINER_CLEANED,
        )
        assert handler.current_state is (
            ContainerRefreshProcessState.CONTAINER_CLEANED
        )


class TestRefreshTransitionHandlerCanTransitTo:
    """UNDEFINED branch guards vs. generic active != to_state rule."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_from_undefined_with_invalid_observed_allows_only_invalid(
        self,
    ) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_INVALID,
        )
        handler.bind_active_state(ContainerRefreshProcessState.UNDEFINED)
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_INVALID,
        ) is True
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_HEALTHY,
        ) is False
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_UPDATED,
        ) is False

    def test_from_undefined_with_non_invalid_observed_allows_only_healthy(
        self,
    ) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.UNDEFINED,
        )
        handler.bind_active_state(ContainerRefreshProcessState.UNDEFINED)
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_HEALTHY,
        ) is True
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_INVALID,
        ) is False
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY,
        ) is False

    def test_other_states_allow_any_different_target(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
        )
        handler.bind_active_state(
            ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
        )
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
        ) is False
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED,
        ) is True
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_UPDATED,
        ) is True

    def test_active_state_takes_precedence_over_observed_state(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_INVALID,
        )
        handler.bind_active_state(
            ContainerRefreshProcessState.CONTAINER_CLEANED,
        )
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_CLEANED,
        ) is False
        assert handler.can_transit_to(
            ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
        ) is True


class TestRefreshTransitionHandlerPerformStateTransition:
    """Capability loader convention + container_cleaned special case."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_noop_when_observed_state_matches_target(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
        )
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityLoader",
        ) as loader_cls, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityExecutor",
        ) as executor:
            handler.perform_state_transition(
                ContainerRefreshProcessState.CONTAINER_HEALTHY,
            )
        loader_cls.assert_not_called()
        executor.execute.assert_not_called()
        assert handler._last_transition_state is (
            ContainerRefreshProcessState.CONTAINER_HEALTHY
        )

    @pytest.mark.parametrize("member_name,state_name", [
        ("CONTAINER_DATASETS_HEALTHY", "container_datasets_healthy"),
        ("CONTAINER_DATAPACKAGE_UPDATED", "container_datapackage_updated"),
        ("CONTAINER_RO_CRATE_UPDATED", "container_ro_crate_updated"),
    ])
    def test_dispatches_standard_capabilities_via_loader_convention(
        self,
        member_name: str,
        state_name: str,
    ) -> None:
        target: ContainerRefreshProcessStatePort = getattr(
            ContainerRefreshProcessState, member_name,
        )
        handler, context, _ = _make_handler(self.workspace)
        fake_cap_type: Any = MagicMock()
        fake_capability: Any = MagicMock()
        fake_cap_type.return_value = fake_capability
        fake_loader: Any = MagicMock()
        fake_loader.get.return_value = fake_cap_type
        expected_id: str = (
            "org.ontobdc.container.plugin.capability.transformation.target."
            f"{state_name}"
        )
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityLoader",
            return_value=fake_loader,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityExecutor",
        ) as executor, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".StrategyParamResolver",
        ) as resolver_cls, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".ResolverLoader",
        ) as resolver_loader_cls:
            handler.perform_state_transition(target)

        fake_loader.get.assert_called_once_with(expected_id)
        fake_cap_type.assert_called_once_with()
        resolver_cls.assert_called_once_with(resolver_loader_cls.return_value)
        executor.execute.assert_called_once_with(
            fake_capability,
            context,
            resolver_cls.return_value,
        )
        assert handler._last_transition_state is target

    def test_container_cleaned_uses_injected_cleanup_capability_directly(
        self,
    ) -> None:
        cleanup: ContainerCleanedCapability = MagicMock(
            spec=ContainerCleanedCapability,
        )
        handler, context, _ = _make_handler(
            self.workspace,
            cleanup_capability=cleanup,
        )
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityLoader",
        ) as loader_cls, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityExecutor",
        ) as executor, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".StrategyParamResolver",
        ) as resolver_cls, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".ResolverLoader",
        ) as resolver_loader_cls:
            handler.perform_state_transition(
                ContainerRefreshProcessState.CONTAINER_CLEANED,
            )

        loader_cls.assert_not_called()
        resolver_cls.assert_called_once_with(resolver_loader_cls.return_value)
        executor.execute.assert_called_once_with(
            cleanup,
            context,
            resolver_cls.return_value,
        )
        assert handler._last_transition_state is (
            ContainerRefreshProcessState.CONTAINER_CLEANED
        )

    def test_missing_capability_raises_value_error(self) -> None:
        handler, _, _ = _make_handler(self.workspace)
        fake_loader: Any = MagicMock()
        fake_loader.get.return_value = None
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityLoader",
            return_value=fake_loader,
        ):
            with pytest.raises(ValueError, match="capability not found"):
                handler.perform_state_transition(
                    ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY,
                )

    def test_capability_exception_propagates_and_keeps_last_transition_clear(
        self,
    ) -> None:
        handler, _, _ = _make_handler(self.workspace)
        fake_cap_type: Any = MagicMock()
        fake_capability: Any = MagicMock()
        fake_cap_type.return_value = fake_capability
        fake_loader: Any = MagicMock()
        fake_loader.get.return_value = fake_cap_type
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityLoader",
            return_value=fake_loader,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".CapabilityExecutor",
        ) as executor, patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".StrategyParamResolver",
        ):
            executor.execute.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError, match="boom"):
                handler.perform_state_transition(
                    ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY,
                )
        assert handler._last_transition_state is None


class TestRefreshTransitionHandlerValidateStateTransition:
    """Same/different states, absent-from-sequence and index comparison."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_same_from_and_to_returns_false(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
        )
        assert handler.validate_state_transition(
            from_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
            to_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
        ) is False

    def test_observed_state_absent_from_sequence_raises(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_INVALID,
        )
        with pytest.raises(ValueError, match="absent from"):
            handler.validate_state_transition(
                from_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
                to_state=ContainerRefreshProcessState.CONTAINER_UPDATED,
            )

    def test_target_state_absent_from_sequence_raises(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
        )
        fake_target: Any = MagicMock()
        fake_target.value = "__absent_never_seen__"
        with pytest.raises(ValueError, match="absent from"):
            handler.validate_state_transition(
                from_state=ContainerRefreshProcessState.UNDEFINED,
                to_state=fake_target,
            )

    def test_observed_at_or_beyond_target_returns_true(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=(
                ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED
            ),
        )
        assert handler.validate_state_transition(
            from_state=ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
            to_state=ContainerRefreshProcessState.CONTAINER_CLEANED,
        ) is True

    def test_observed_before_target_returns_false(self) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_HEALTHY,
        )
        assert handler.validate_state_transition(
            from_state=ContainerRefreshProcessState.UNDEFINED,
            to_state=ContainerRefreshProcessState.CONTAINER_UPDATED,
        ) is False


class TestRefreshTransitionHandlerExecuteAndFinalResponse:
    """Worker delegation and both response shapes (OK vs. INVALID)."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_execute_delegates_to_state_worker_and_builds_response(
        self,
    ) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_UPDATED,
        )
        visited: List[str] = [
            "undefined",
            "container_healthy",
            "container_datasets_healthy",
            "container_cleaned",
            "container_datapackage_updated",
            "container_ro_crate_updated",
            "container_updated",
        ]
        fake_worker: Any = MagicMock()
        fake_worker.work.return_value = list(visited)
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".StateWorkerAdapter",
            return_value=fake_worker,
        ) as worker_cls:
            response: CommandResponse = handler.execute()
        worker_cls.assert_called_once()
        call_kwargs: Any = worker_cls.call_args
        assert call_kwargs.kwargs["state_adapter"] is ContainerRefreshProcessState
        assert call_kwargs.kwargs["state_context_name"] == (
            "ContainerRefreshProcessStatePort"
        )
        assert call_kwargs.kwargs["handler"] is handler
        assert isinstance(response, CommandResponse)
        assert response.content["visited_states"] == visited
        assert response.content["current_state"] == (
            ContainerRefreshProcessState.CONTAINER_UPDATED.value
        )
        assert "container_id" in response.content
        assert "path" in response.content
        assert "exists" not in response.content

    def test_build_final_response_uses_exception_command_when_invalid(
        self,
    ) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=ContainerRefreshProcessState.CONTAINER_INVALID,
        )
        visited: List[str] = ["undefined", "container_invalid"]
        response: CommandResponse = handler._build_final_response(visited)
        assert isinstance(response, ExceptionCommandResponse)
        assert response.title == "Invalid Storage Container"
        assert response.content["visited_states"] == visited
        assert response.content["current_state"] == (
            ContainerRefreshProcessState.CONTAINER_INVALID.value
        )
        assert "path" in response.content
        assert "container_id" in response.content

    def test_build_final_response_returns_success_for_healthy_states(
        self,
    ) -> None:
        handler, _, _ = _make_handler(
            self.workspace,
            evaluator_state=(
                ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED
            ),
        )
        visited: List[str] = [
            "undefined",
            "container_healthy",
            "container_datasets_healthy",
            "container_cleaned",
            "container_datapackage_updated",
        ]
        response: CommandResponse = handler._build_final_response(visited)
        assert type(response).__name__ == "CommandResponse"
        assert not isinstance(response, ExceptionCommandResponse)
        assert response.title == "Storage Container Updated"
        assert response.content["path"] == str(
            self.workspace.container_path.resolve(),
        )
        assert response.content["container_id"] == "container-xyz"
