from pathlib import Path
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateProcessStatePort,
)
from ontobdc.container.plugin.machine.container_create.machine import (
    ContainerCreateStateEvaluatorAdapter,
)
from ontobdc.container.plugin.machine.container_create.state import (
    ContainerCreateProcessState,
)
from test.check.container.container_workspace import ContainerCheckWorkspace


class TestContainerCreateStateEvaluatorAdapterUndefinedAndInvalid:
    """Disk-based early states: target absent or target is a file."""

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()
        self.evaluator: ContainerCreateStateEvaluatorAdapter = (
            ContainerCreateStateEvaluatorAdapter()
        )

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def _build_context(
        self,
        container_path: Path,
    ) -> CliContextPort:
        context: CliContextPort = Mock(spec=CliContextPort)
        context.root_path = str(self.workspace.root_path)
        context.get_parameter_value.return_value = str(container_path)
        return context

    def test_evaluate_returns_undefined_when_target_does_not_exist(self) -> None:
        missing_container: Path = self.workspace.container_path / "absent"
        context: CliContextPort = self._build_context(missing_container)

        state: ContainerCreateProcessStatePort = self.evaluator.evaluate(context)

        assert state is ContainerCreateProcessState.UNDEFINED

    def test_evaluate_returns_invalid_path_when_target_is_a_regular_file(
        self,
    ) -> None:
        import shutil
        shutil.rmtree(self.workspace.container_path)
        file_as_target: Path = self.workspace.root_path / "pretend-container"
        file_as_target.write_text("not a dir", encoding="utf-8")
        context: CliContextPort = self._build_context(file_as_target)

        state: ContainerCreateProcessStatePort = self.evaluator.evaluate(context)

        assert state is ContainerCreateProcessState.INVALID_PATH

    def test_evaluate_returns_directory_ready_when_dir_exists_without_state_files(
        self,
    ) -> None:
        context: CliContextPort = self._build_context(self.workspace.container_path)

        state: ContainerCreateProcessStatePort = self.evaluator.evaluate(context)

        assert state is ContainerCreateProcessState.DIRECTORY_READY

    def test_evaluate_resolves_user_home_and_relative_paths(self) -> None:
        nested_target: Path = self.workspace.container_path / "subdir"
        nested_target.mkdir()
        context: CliContextPort = Mock(spec=CliContextPort)
        context.root_path = str(self.workspace.root_path)
        context.get_parameter_value.return_value = (
            f"{self.workspace.root_path}/{self.workspace.CONTAINER_DIRECTORY_NAME}/subdir"
        )

        state: ContainerCreateProcessStatePort = self.evaluator.evaluate(context)

        assert state is ContainerCreateProcessState.DIRECTORY_READY


class TestContainerCreateStateEvaluatorAdapterProgressiveChecks:
    """Simulate progressive check pass/fail using mocked ``_check_for``.

    The real check scripts are already covered in ``test/check/container``,
    so the evaluator unit tests focus on the sequencing contract: return
    the *last* state whose check returned zero, walking the sequence after
    DIRECTORY_READY.
    """

    STATE_SEQUENCE: Any = [
        ContainerCreateProcessState.DIRECTORY_READY,
        ContainerCreateProcessState.CONTAINER_METADATA_READY,
        ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
        ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED,
    ]

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()
        self.evaluator: ContainerCreateStateEvaluatorAdapter = (
            ContainerCreateStateEvaluatorAdapter()
        )

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def _build_context(self) -> CliContextPort:
        context: CliContextPort = Mock(spec=CliContextPort)
        context.root_path = str(self.workspace.root_path)
        context.get_parameter_value.return_value = str(self.workspace.container_path)
        return context

    @staticmethod
    def _make_check_function(passes: bool) -> Callable[..., int]:
        def _main(root_path: str, container_path: str) -> int:
            return 0 if passes else 1
        return _main

    def test_first_check_failing_keeps_directory_ready(self) -> None:
        from unittest.mock import patch
        context: CliContextPort = self._build_context()

        def fake_check_for(
            cls: Any, state: ContainerCreateProcessStatePort,
        ) -> Callable[..., int]:
            return self._make_check_function(False)

        with patch.object(
            ContainerCreateStateEvaluatorAdapter, "_check_for",
            classmethod(fake_check_for),
        ):
            state: ContainerCreateProcessStatePort = self.evaluator.evaluate(context)

        assert state is ContainerCreateProcessState.DIRECTORY_READY

    @pytest.mark.parametrize("passing_count", [1, 2, 3])
    def test_n_passing_checks_land_on_the_nth_sequence_state(
        self, passing_count: int,
    ) -> None:
        from unittest.mock import patch
        context: CliContextPort = self._build_context()
        post_directory: Any = list(self.STATE_SEQUENCE[1:])

        def fake_check_for(
            cls: Any, state: ContainerCreateProcessStatePort,
        ) -> Callable[..., int]:
            state_index: int = post_directory.index(state)
            passes: bool = state_index < passing_count
            return self._make_check_function(passes)

        with patch.object(
            ContainerCreateStateEvaluatorAdapter, "_check_for",
            classmethod(fake_check_for),
        ):
            reached: ContainerCreateProcessStatePort = (
                self.evaluator.evaluate(context)
            )

        assert reached is self.STATE_SEQUENCE[passing_count]

    def test_all_checks_passing_lands_on_container_manifest_synced(self) -> None:
        from unittest.mock import patch
        context: CliContextPort = self._build_context()

        def fake_check_for(
            cls: Any, state: ContainerCreateProcessStatePort,
        ) -> Callable[..., int]:
            return self._make_check_function(True)

        with patch.object(
            ContainerCreateStateEvaluatorAdapter, "_check_for",
            classmethod(fake_check_for),
        ):
            reached: ContainerCreateProcessStatePort = (
                self.evaluator.evaluate(context)
            )

        assert reached is ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED


class TestContainerCreateStateEvaluatorAdapterCheckFor:
    """Verify the ``is_<state>.check.main`` module naming convention."""

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
    def test_check_for_loads_the_expected_plugin_entry_point(
        self,
        state: ContainerCreateProcessStatePort,
        expected_state_name: str,
    ) -> None:
        check: Callable[..., int] = (
            ContainerCreateStateEvaluatorAdapter._check_for(state)
        )
        expected_module: str = (
            f"{ContainerCreateStateEvaluatorAdapter.CHECK_MODULE_PREFIX}"
            f"{expected_state_name}.check"
        )
        assert callable(check)
        assert check.__module__.startswith(expected_module)

    def test_check_for_raises_type_error_when_main_is_not_callable(self) -> None:
        import importlib
        from unittest.mock import patch
        fake_module: Any = Mock()
        fake_module.main = "not a function"
        with patch.object(importlib, "import_module", return_value=fake_module):
            with pytest.raises(TypeError, match="is not callable"):
                ContainerCreateStateEvaluatorAdapter._check_for(
                    ContainerCreateProcessState.CONTAINER_METADATA_READY,
                )
