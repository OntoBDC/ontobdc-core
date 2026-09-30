from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from ontobdc.container.plugin.machine.container_refresh.state import (
    ContainerRefreshProcessState,
)
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateTransitionHandler,
)


class TestContainerRefreshStatechartPath:
    """Verify the static YAML path is discoverable via the handler locator."""

    def test_get_statechart_file_path_returns_an_existing_yaml_file(self) -> None:
        statechart_path: Path = (
            ContainerRefreshStateTransitionHandler._get_statechart_file_path()
        )
        assert isinstance(statechart_path, Path)
        assert statechart_path.is_file()
        assert statechart_path.suffix == ".yaml"
        assert statechart_path.name == "standard_container_refresh.yaml"

    def test_path_points_to_the_expected_python_package_directory(self) -> None:
        statechart_path: Path = (
            ContainerRefreshStateTransitionHandler._get_statechart_file_path()
        )
        parent: Path = statechart_path.parent
        assert (parent / "state.py").is_file()
        assert (parent / "machine.py").is_file()


class TestContainerRefreshStatechartData:
    """Verify the YAML contents load as a structural statechart."""

    def test_data_returns_a_nested_statechart_mapping(self) -> None:
        data: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()
        )
        assert isinstance(data, dict)
        assert "statechart" in data
        statechart: Any = data["statechart"]
        assert isinstance(statechart, dict)
        assert "root state" in statechart
        root_state: Any = statechart["root state"]
        assert isinstance(root_state, dict)
        assert "initial" in root_state
        assert "states" in root_state
        states: Any = root_state["states"]
        assert isinstance(states, list)
        expected_count: int = len(
            [v for v in ContainerRefreshProcessState.__dict__.values()
             if isinstance(v, str) and v.startswith("__")]
        )
        assert len(states) == expected_count

    def test_every_state_declaration_has_a_unique_name(self) -> None:
        root: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()[
                "statechart"
            ]["root state"]
        )
        states: Any = root["states"]
        names: List[str] = [state["name"] for state in states]
        assert len(names) == len(set(names))
        expected_names: List[str] = [
            member.value.strip("_")
            for member in ContainerRefreshProcessState
            if isinstance(member.value, str) and member.value.startswith("__")
        ]
        for expected in expected_names:
            assert expected in names

    def test_statechart_data_raises_when_yaml_is_not_a_mapping(self) -> None:
        fake_path: Any = Path(__file__)
        with patch.object(
            ContainerRefreshStateTransitionHandler,
            "_get_statechart_file_path",
            return_value=fake_path,
        ):
            with patch("pathlib.Path.read_text", return_value="[1, 2, 3]"):
                with pytest.raises(TypeError, match="must be a mapping"):
                    ContainerRefreshStateTransitionHandler._statechart_data()


class TestContainerRefreshStatechartSequence:
    """Verify the machine produces the expected full operational sequence."""

    EXPECTED_SEQUENCE: List[str] = [
        "undefined",
        "container_healthy",
        "container_datasets_healthy",
        "container_cleaned",
        "container_datapackage_updated",
        "container_ro_crate_updated",
        "container_updated",
    ]

    def test_sequence_contains_seven_elements(self) -> None:
        sequence: List[str] = (
            ContainerRefreshStateTransitionHandler._state_sequence()
        )
        assert isinstance(sequence, list)
        assert len(sequence) == 7

    def test_sequence_starts_at_undefined_and_ends_at_container_updated(
        self,
    ) -> None:
        sequence: List[str] = (
            ContainerRefreshStateTransitionHandler._state_sequence()
        )
        assert sequence == self.EXPECTED_SEQUENCE

    def test_sequence_matches_the_operational_state_order(self) -> None:
        sequence: List[str] = (
            ContainerRefreshStateTransitionHandler._state_sequence()
        )
        prior_index: int = -1
        member_names: List[str] = [
            "UNDEFINED",
            "CONTAINER_HEALTHY",
            "CONTAINER_DATASETS_HEALTHY",
            "CONTAINER_CLEANED",
            "CONTAINER_DATAPACKAGE_UPDATED",
            "CONTAINER_RO_CRATE_UPDATED",
            "CONTAINER_UPDATED",
        ]
        for index, member_name in enumerate(member_names):
            member: ContainerRefreshProcessState = getattr(
                ContainerRefreshProcessState, member_name,
            )
            state_name: str = member.value.strip("_")
            assert sequence[index] == state_name
            assert sequence.index(state_name) == prior_index + 1
            prior_index = sequence.index(state_name)

    def test_sequence_raises_when_initial_state_is_missing(self) -> None:
        data: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()
        )
        root: Dict[str, Any] = data["statechart"]["root state"]
        root["initial"] = None
        with patch.object(
            ContainerRefreshStateTransitionHandler,
            "_statechart_data",
            return_value=data,
        ):
            with pytest.raises(ValueError, match="declare a root initial state"):
                ContainerRefreshStateTransitionHandler._state_sequence()

    def test_sequence_branch_picks_operational_target_over_container_invalid(
        self,
    ) -> None:
        data: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()
        )
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        undefined_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "undefined"
        )
        undefined_state["transitions"] = [
            {"target": "container_invalid"},
            {"target": "container_cleaned"},
            {"target": "container_updated"},
        ]
        with patch.object(
            ContainerRefreshStateTransitionHandler,
            "_statechart_data",
            return_value=data,
        ):
            sequence: List[str] = (
                ContainerRefreshStateTransitionHandler._state_sequence()
            )
        assert sequence[0] == "undefined"
        assert sequence[1] == "container_updated"

    def test_sequence_falls_back_to_container_invalid_when_no_other_target_exists(
        self,
    ) -> None:
        data: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()
        )
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        undefined_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "undefined"
        )
        undefined_state["transitions"] = [
            {"target": "container_invalid"},
            {"target": "container_invalid"},
        ]
        with patch.object(
            ContainerRefreshStateTransitionHandler,
            "_statechart_data",
            return_value=data,
        ):
            sequence: List[str] = (
                ContainerRefreshStateTransitionHandler._state_sequence()
            )
        assert sequence == ["undefined", "container_invalid"]

    def test_sequence_raises_when_a_transition_is_not_a_mapping(self) -> None:
        data: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()
        )
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        healthy_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "container_healthy"
        )
        healthy_state["transitions"] = ["not a dict"]
        with patch.object(
            ContainerRefreshStateTransitionHandler,
            "_statechart_data",
            return_value=data,
        ):
            sequence: List[str] = (
                ContainerRefreshStateTransitionHandler._state_sequence()
            )
            assert sequence[-1] == "container_healthy"

    def test_sequence_raises_when_a_target_is_empty(self) -> None:
        data: Dict[str, Any] = (
            ContainerRefreshStateTransitionHandler._statechart_data()
        )
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        healthy_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "container_healthy"
        )
        healthy_state["transitions"] = [{"target": ""}]
        with patch.object(
            ContainerRefreshStateTransitionHandler,
            "_statechart_data",
            return_value=data,
        ):
            sequence: List[str] = (
                ContainerRefreshStateTransitionHandler._state_sequence()
            )
            assert sequence[-1] == "container_healthy"
