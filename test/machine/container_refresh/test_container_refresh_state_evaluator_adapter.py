from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshProcessStatePort,
)
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateEvaluatorAdapter,
    ContainerRefreshStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_refresh.state import (
    ContainerRefreshProcessState,
)
from test.check.container.container_workspace import ContainerCheckWorkspace


class TestContainerRefreshStateEvaluatorAdapterInvalidAndUndefined:
    """Early states: invalid path type, missing dir, or core checks failing."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()
        self.evaluator: ContainerRefreshStateEvaluatorAdapter = (
            ContainerRefreshStateEvaluatorAdapter()
        )

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def _build_context(
        self,
        container_path: Any,
    ) -> CliContextPort:
        context: CliContextPort = Mock(spec=CliContextPort)
        context.root_path = str(self.workspace.root_path)
        context.get_parameter_value.return_value = container_path
        return context

    def test_evaluate_returns_invalid_when_container_path_has_wrong_type(
        self,
    ) -> None:
        context: CliContextPort = self._build_context(42)
        state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(context)
        assert state is ContainerRefreshProcessState.CONTAINER_INVALID

    def test_evaluate_returns_invalid_when_container_path_is_none(self) -> None:
        context: CliContextPort = self._build_context(None)
        state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(context)
        assert state is ContainerRefreshProcessState.CONTAINER_INVALID

    def test_evaluate_returns_invalid_when_target_is_a_regular_file(
        self,
    ) -> None:
        import shutil
        shutil.rmtree(self.workspace.container_path)
        file_as_target: Path = self.workspace.root_path / "pretend-container"
        file_as_target.write_text("not a dir", encoding="utf-8")
        context: CliContextPort = self._build_context(str(file_as_target))

        state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(context)

        assert state is ContainerRefreshProcessState.CONTAINER_INVALID

    def test_evaluate_returns_undefined_when_metadata_check_fails(self) -> None:
        context: CliContextPort = self._build_context(
            str(self.workspace.container_path),
        )
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_metadata_ready",
            return_value=1,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_storage_index_ready",
            return_value=0,
        ):
            state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(
                context,
            )

        assert state is ContainerRefreshProcessState.UNDEFINED

    def test_evaluate_returns_undefined_when_storage_index_check_fails(
        self,
    ) -> None:
        context: CliContextPort = self._build_context(
            str(self.workspace.container_path),
        )
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_metadata_ready",
            return_value=0,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_storage_index_ready",
            return_value=2,
        ):
            state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(
                context,
            )

        assert state is ContainerRefreshProcessState.UNDEFINED

    def test_evaluate_resolves_user_home_and_relative_paths(self) -> None:
        nested_target: Path = self.workspace.container_path / "subdir"
        nested_target.mkdir()
        context: CliContextPort = Mock(spec=CliContextPort)
        context.root_path = str(self.workspace.root_path)
        context.get_parameter_value.return_value = (
            f"{self.workspace.root_path}/{self.workspace.CONTAINER_DIRECTORY_NAME}/subdir"
        )

        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_metadata_ready",
            return_value=1,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_storage_index_ready",
            return_value=0,
        ):
            state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(
                context,
            )

        assert state is ContainerRefreshProcessState.UNDEFINED


class TestContainerRefreshStateEvaluatorAdapterProgressiveStates:
    """Post-HEALTHY progressive states via mocked state_was_reached and events."""

    STATE_ORDER: Any = [
        ContainerRefreshProcessState.CONTAINER_HEALTHY,
        ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY,
        ContainerRefreshProcessState.CONTAINER_CLEANED,
        ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
        ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED,
        ContainerRefreshProcessState.CONTAINER_UPDATED,
    ]

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()
        self.evaluator: ContainerRefreshStateEvaluatorAdapter = (
            ContainerRefreshStateEvaluatorAdapter()
        )

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def _build_context(self) -> CliContextPort:
        context: CliContextPort = Mock(spec=CliContextPort)
        context.root_path = str(self.workspace.root_path)
        context.get_parameter_value.return_value = str(
            self.workspace.container_path,
        )
        return context

    @pytest.mark.parametrize("passing_count", [1, 2, 3, 4, 5, 6])
    def test_evaluate_returns_the_last_passing_sequential_state(
        self,
        passing_count: int,
    ) -> None:
        expected: ContainerRefreshProcessStatePort = self.STATE_ORDER[
            passing_count - 1
        ]
        counter: dict = {"n": 0}

        def fake_state_was_reached(**_: Any) -> bool:
            counter["n"] += 1
            return counter["n"] <= passing_count - 1

        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_metadata_ready",
            return_value=0,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_storage_index_ready",
            return_value=0,
        ), patch.object(
            ContainerRefreshStateEvaluatorAdapter,
            "_state_was_reached",
            side_effect=fake_state_was_reached,
        ):
            state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(
                self._build_context(),
            )

        assert state is expected

    def test_evaluate_returns_container_healthy_when_first_subsequent_state_fails(
        self,
    ) -> None:
        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_metadata_ready",
            return_value=0,
        ), patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_storage_index_ready",
            return_value=0,
        ), patch.object(
            ContainerRefreshStateEvaluatorAdapter,
            "_state_was_reached",
            return_value=False,
        ):
            state: ContainerRefreshProcessStatePort = self.evaluator.evaluate(
                self._build_context(),
            )

        assert state is ContainerRefreshProcessState.CONTAINER_HEALTHY


class TestContainerRefreshStateEvaluatorAdapterStateWasReached:
    """Direct unit coverage of the ``_state_was_reached`` dispatch table."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def _events_directory(self) -> Path:
        return (
            ContainerRefreshStateTransitionHandler._refresh_events_directory(
                self.workspace.container_path,
            )
        )

    def test_datasets_healthy_passes_when_event_file_exists(self) -> None:
        events_dir: Path = self._events_directory()
        events_dir.mkdir(parents=True, exist_ok=True)
        event_file: Path = events_dir / "__container_datasets_healthy__.json"
        event_file.write_text("{}", encoding="utf-8")
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        result: bool = (
            ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                state_enum=ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY,
                state_name="container_datasets_healthy",
                container_path=self.workspace.container_path,
                root_path=self.workspace.root_path,
                cleanup_capability=cleanup,
                events_directory=events_dir,
            )
        )
        assert result is True

    def test_container_updated_passes_when_event_file_exists(self) -> None:
        events_dir: Path = self._events_directory()
        events_dir.mkdir(parents=True, exist_ok=True)
        event_file: Path = events_dir / "__container_updated__.json"
        event_file.write_text("{}", encoding="utf-8")
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        result: bool = (
            ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                state_enum=ContainerRefreshProcessState.CONTAINER_UPDATED,
                state_name="container_updated",
                container_path=self.workspace.container_path,
                root_path=self.workspace.root_path,
                cleanup_capability=cleanup,
                events_directory=events_dir,
            )
        )
        assert result is True

    def test_event_file_states_fail_when_event_file_is_absent(self) -> None:
        events_dir: Path = self._events_directory()
        events_dir.mkdir(parents=True, exist_ok=True)
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        result: bool = (
            ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                state_enum=ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY,
                state_name="container_datasets_healthy",
                container_path=self.workspace.container_path,
                root_path=self.workspace.root_path,
                cleanup_capability=cleanup,
                events_directory=events_dir,
            )
        )
        assert result is False

    def test_container_cleaned_uses_evaluate_container_cleaned(self) -> None:
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = ["stale.bin"]

        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".evaluate_container_cleaned",
            return_value=0,
        ) as mocked:
            result: bool = (
                ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                    state_enum=ContainerRefreshProcessState.CONTAINER_CLEANED,
                    state_name="container_cleaned",
                    container_path=self.workspace.container_path,
                    root_path=self.workspace.root_path,
                    cleanup_capability=cleanup,
                    events_directory=self._events_directory(),
                )
            )

        assert result is True
        mocked.assert_called_once_with(
            container_path=str(self.workspace.container_path),
            file_names=["stale.bin"],
        )

    def test_container_datapackage_updated_uses_its_evaluator(self) -> None:
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".evaluate_container_datapackage_updated",
            return_value=0,
        ) as mocked:
            result: bool = (
                ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                    state_enum=(
                        ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED
                    ),
                    state_name="container_datapackage_updated",
                    container_path=self.workspace.container_path,
                    root_path=self.workspace.root_path,
                    cleanup_capability=cleanup,
                    events_directory=self._events_directory(),
                )
            )

        assert result is True
        mocked.assert_called_once_with(str(self.workspace.container_path))

    def test_container_ro_crate_updated_uses_manifest_synced_check(self) -> None:
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        with patch(
            "ontobdc.container.plugin.machine.container_refresh.machine"
            ".check_container_manifest_synced",
            return_value=0,
        ) as mocked:
            result: bool = (
                ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                    state_enum=(
                        ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED
                    ),
                    state_name="container_ro_crate_updated",
                    container_path=self.workspace.container_path,
                    root_path=self.workspace.root_path,
                    cleanup_capability=cleanup,
                    events_directory=self._events_directory(),
                )
            )

        assert result is True
        mocked.assert_called_once_with(
            root_path=str(self.workspace.root_path),
            container_path=str(self.workspace.container_path),
        )

    @pytest.mark.parametrize("state_name", ["undefined", "container_invalid"])
    def test_presequence_states_never_count_as_reached(
        self,
        state_name: str,
    ) -> None:
        state_enum: ContainerRefreshProcessStatePort = (
            ContainerRefreshProcessState.get_state(state_name)
        )
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        result: bool = (
            ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                state_enum=state_enum,
                state_name=state_name,
                container_path=self.workspace.container_path,
                root_path=self.workspace.root_path,
                cleanup_capability=cleanup,
                events_directory=self._events_directory(),
            )
        )
        assert result is False

    def test_state_was_reached_raises_when_enum_value_is_not_string(self) -> None:
        bad_state: Any = Mock()
        bad_state.value = None
        cleanup: Any = Mock()
        cleanup.file_names_to_clean = []

        with pytest.raises(TypeError, match="non-empty string 'value'"):
            ContainerRefreshStateEvaluatorAdapter._state_was_reached(
                state_enum=bad_state,
                state_name="container_cleaned",
                container_path=self.workspace.container_path,
                root_path=self.workspace.root_path,
                cleanup_capability=cleanup,
                events_directory=self._events_directory(),
            )
