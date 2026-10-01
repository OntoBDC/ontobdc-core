from typing import Dict, List, Tuple
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.plugin.parameter.container import ContainerIdStrategy

_CONTAINER_ID: str = "urn:uuid:3ae5682a-0d95-458c-92b8-54c78f533d9b"
_INVALID_CONTAINER_ID: str = "urn:uuid:00000000-0000-0000-0000-000000000000"


class ContainerContextHarness:
    """In-memory context used to observe parameter strategy effects."""

    def __init__(
        self,
        raw_args: List[str],
        values: Dict[str, str],
        root_path: str,
    ) -> None:
        self.values: Dict[str, str] = values
        self.context: CliContextPort = Mock(spec=CliContextPort)
        self.context.root_path = root_path
        self.context.raw_args = raw_args
        self.context.has_parameter.side_effect = self.has_parameter
        self.context.get_parameter_value.side_effect = self.get_parameter_value
        self.context.set_parameter_value.side_effect = self.set_parameter_value
        self.context.delete_parameter.side_effect = self.delete_parameter

    def has_parameter(self, parameter_name: str) -> bool:
        return parameter_name in self.values

    def get_parameter_value(self, parameter_name: str) -> str:
        return self.values[parameter_name]

    def set_parameter_value(self, parameter_name: str, value: str) -> None:
        self.values[parameter_name] = value

    def delete_parameter(self, parameter_name: str) -> None:
        self.values.pop(parameter_name)

    def assert_resolved(self, container_path: Path) -> None:
        assert self.values["container_id"] == _CONTAINER_ID
        assert self.values["container_path"] == str(container_path.resolve())

    def assert_unresolved(self) -> None:
        assert "container_id" not in self.values
        assert "container_path" not in self.values


class TestContainerIdStrategy:
    """Unit coverage for every supported container selector."""

    @staticmethod
    def _registered(container_path: Path) -> Tuple[Tuple[str, Path], ...]:
        return ((_CONTAINER_ID, container_path.resolve()),)

    def _execute(
        self,
        harness: ContainerContextHarness,
        container_path: Path,
    ) -> None:
        strategy: ContainerIdStrategy = ContainerIdStrategy()
        registered: Tuple[Tuple[str, Path], ...] = self._registered(container_path)

        with patch.object(
            strategy,
            "_registered_containers",
            return_value=registered,
        ):
            strategy.execute(harness.context)

    def _assert_result(
        self,
        harness: ContainerContextHarness,
        container_path: Path,
        valid: bool,
    ) -> None:
        self._execute(harness, container_path)
        if valid:
            harness.assert_resolved(container_path)
            return

        harness.assert_unresolved()

    def test_clears_container_values_before_resolution(self) -> None:
        values: Dict[str, str] = {
            "container_id": "stale-container-id",
            "container_path": "/stale/container/path",
        }
        harness: ContainerContextHarness = ContainerContextHarness(
            [],
            values,
            "/project/root",
        )
        strategy: ContainerIdStrategy = ContainerIdStrategy()

        def registered_containers(
            root_path: str,
        ) -> Tuple[Tuple[str, Path], ...]:
            assert root_path == harness.context.root_path
            harness.assert_unresolved()
            return ()

        with (
            patch.object(
                strategy,
                "_registered_containers",
                side_effect=registered_containers,
            ),
            patch.object(
                strategy,
                "_resolve_container_for_current_directory",
                return_value=None,
            ),
        ):
            strategy.execute(harness.context)

        assert harness.context.delete_parameter.call_args_list == [
            call("container_id"),
            call("container_path"),
        ]
        harness.assert_unresolved()

    @pytest.mark.parametrize("valid", [True, False])
    def test_container_selector_with_id(
        self,
        tmp_path: Path,
        valid: bool,
    ) -> None:
        container_path: Path = tmp_path / "container"
        container_path.mkdir()
        selector: str = _CONTAINER_ID if valid else _INVALID_CONTAINER_ID
        harness: ContainerContextHarness = ContainerContextHarness(
            ["container", "--container", selector, "--inspect"],
            {
                "container": selector,
                "container_id": "stale-container-id",
                "container_path": "/stale/container/path",
            },
            str(tmp_path),
        )

        self._assert_result(harness, container_path, valid)

    @pytest.mark.parametrize("valid", [True, False])
    def test_container_selector_with_path(
        self,
        tmp_path: Path,
        valid: bool,
    ) -> None:
        container_path: Path = tmp_path / "container"
        container_path.mkdir()
        invalid_path: Path = tmp_path / "missing"
        selector: str = str(container_path if valid else invalid_path)
        harness: ContainerContextHarness = ContainerContextHarness(
            ["container", "--container", selector, "--inspect"],
            {
                "container": selector,
                "container_id": "stale-container-id",
                "container_path": "/stale/container/path",
            },
            str(tmp_path),
        )

        self._assert_result(harness, container_path, valid)

    @pytest.mark.parametrize("valid", [True, False])
    def test_container_id_selector(
        self,
        tmp_path: Path,
        valid: bool,
    ) -> None:
        container_path: Path = tmp_path / "container"
        container_path.mkdir()
        selector: str = _CONTAINER_ID if valid else _INVALID_CONTAINER_ID
        harness: ContainerContextHarness = ContainerContextHarness(
            ["container", "--container-id", selector, "--inspect"],
            {
                "container_id": selector,
                "container_path": "/stale/container/path",
            },
            str(tmp_path),
        )

        self._assert_result(harness, container_path, valid)

    @pytest.mark.parametrize("valid", [True, False])
    def test_container_path_selector(
        self,
        tmp_path: Path,
        valid: bool,
    ) -> None:
        container_path: Path = tmp_path / "container"
        container_path.mkdir()
        invalid_path: Path = tmp_path / "missing"
        selector: str = str(container_path if valid else invalid_path)
        harness: ContainerContextHarness = ContainerContextHarness(
            ["container", "--container-path", selector, "--inspect"],
            {
                "container_id": "stale-container-id",
                "container_path": selector,
            },
            str(tmp_path),
        )

        self._assert_result(harness, container_path, valid)

    @pytest.mark.parametrize("valid", [True, False])
    def test_current_working_directory_selector(
        self,
        tmp_path: Path,
        valid: bool,
    ) -> None:
        container_path: Path = tmp_path / "container"
        container_path.mkdir()
        working_directory: Path = (
            container_path / "nested" if valid else tmp_path / "outside"
        )
        working_directory.mkdir()
        harness: ContainerContextHarness = ContainerContextHarness(
            ["container", "--inspect"],
            {
                "container_id": "stale-container-id",
                "container_path": "/stale/container/path",
            },
            str(tmp_path),
        )

        with patch(
            "ontobdc.container.plugin.parameter.container.os.getcwd",
            return_value=str(working_directory),
        ):
            self._assert_result(harness, container_path, valid)
