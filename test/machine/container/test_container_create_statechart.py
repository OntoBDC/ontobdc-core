from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from ontobdc.container.plugin.machine.container_create.state import (
    ContainerCreateProcessState,
)
from ontobdc.container.plugin.machine.container_create.statechart import (
    ContainerCreateStatechart,
)


class TestContainerCreateStatechartPath:
    """Verify the static YAML path is discoverable via the standard locator."""

    def test_path_returns_an_existing_yaml_file(self) -> None:
        statechart_path: Path = ContainerCreateStatechart.path()
        assert isinstance(statechart_path, Path)
        assert statechart_path.is_file()
        assert statechart_path.suffix == ".yaml"
        assert statechart_path.name == "standard_container_create.yaml"

    def test_path_points_to_the_expected_python_package_directory(self) -> None:
        statechart_path: Path = ContainerCreateStatechart.path()
        parent: Path = statechart_path.parent
        assert (parent / "state.py").is_file()
        assert (parent / "statechart.py").is_file()
        assert (parent / "machine.py").is_file()


class TestContainerCreateStatechartData:
    """Verify the YAML contents load as a structural statechart."""

    def test_data_returns_a_nested_statechart_mapping(self) -> None:
        data: Dict[str, Any] = ContainerCreateStatechart._data()
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
            [v for v in ContainerCreateProcessState.__dict__.values()
             if isinstance(v, str) and v.startswith("__")]
        )
        assert len(states) == expected_count

    def test_every_state_declaration_has_a_unique_name(self) -> None:
        root: Dict[str, Any] = ContainerCreateStatechart._data()[
            "statechart"
        ]["root state"]
        states: Any = root["states"]
        names: List[str] = [state["name"] for state in states]
        assert len(names) == len(set(names))
        expected_names: List[str] = [
            member.value.strip("_")
            for member in ContainerCreateProcessState
            if isinstance(member.value, str) and member.value.startswith("__")
        ]
        for expected in expected_names:
            assert expected in names


class TestContainerCreateStatechartSequence:
    """Verify the machine produces the expected linear post-directory sequence."""

    EXPECTED_SEQUENCE: List[str] = [
        "directory_ready",
        "container_metadata_ready",
        "container_storage_index_ready",
        "container_manifest_synced",
    ]

    def test_sequence_contains_four_elements_after_directory_ready(self) -> None:
        sequence: List[str] = ContainerCreateStatechart.sequence()
        assert isinstance(sequence, list)
        assert len(sequence) == 4

    def test_sequence_starts_at_directory_ready_and_ends_at_manifest_synced(
        self,
    ) -> None:
        sequence: List[str] = ContainerCreateStatechart.sequence()
        assert sequence == self.EXPECTED_SEQUENCE

    def test_sequence_matches_the_linear_state_order(self) -> None:
        sequence: List[str] = ContainerCreateStatechart.sequence()
        prior_index: int = -1
        member_names: List[str] = [
            "DIRECTORY_READY",
            "CONTAINER_METADATA_READY",
            "CONTAINER_STORAGE_INDEX_READY",
            "CONTAINER_MANIFEST_SYNCED",
        ]
        for index, member_name in enumerate(member_names):
            member: ContainerCreateProcessState = getattr(
                ContainerCreateProcessState, member_name,
            )
            state_name: str = member.value.strip("_")
            assert sequence[index] == state_name
            assert sequence.index(state_name) == prior_index + 1
            prior_index = sequence.index(state_name)

    def test_sequence_raises_when_a_state_has_multiple_transitions(self) -> None:
        data: Dict[str, Any] = ContainerCreateStatechart._data()
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        directory_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "directory_ready"
        )
        directory_state["transitions"].append(
            {"target": "container_manifest_synced"},
        )
        with patch.object(
            ContainerCreateStatechart, "_data", return_value=data,
        ):
            with pytest.raises(ValueError, match="linear after"):
                ContainerCreateStatechart.sequence()

    def test_sequence_raises_when_the_yaml_contains_a_cycle(self) -> None:
        data: Dict[str, Any] = ContainerCreateStatechart._data()
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        manifest_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "container_manifest_synced"
        )
        manifest_state["transitions"] = [{"target": "directory_ready"}]
        with patch.object(
            ContainerCreateStatechart, "_data", return_value=data,
        ):
            with pytest.raises(ValueError, match="contains a cycle"):
                ContainerCreateStatechart.sequence()

    def test_sequence_raises_when_a_transition_is_not_a_mapping(self) -> None:
        data: Dict[str, Any] = ContainerCreateStatechart._data()
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        directory_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "directory_ready"
        )
        directory_state["transitions"] = ["not a dict"]
        with patch.object(
            ContainerCreateStatechart, "_data", return_value=data,
        ):
            with pytest.raises(TypeError, match="transition must be a mapping"):
                ContainerCreateStatechart.sequence()

    def test_sequence_raises_when_a_target_is_missing_or_empty(self) -> None:
        data: Dict[str, Any] = ContainerCreateStatechart._data()
        states: List[Dict[str, Any]] = list(
            data["statechart"]["root state"]["states"]
        )
        directory_state: Dict[str, Any] = next(
            s for s in states if s["name"] == "directory_ready"
        )
        directory_state["transitions"] = [{"target": ""}]
        with patch.object(
            ContainerCreateStatechart, "_data", return_value=data,
        ):
            with pytest.raises(TypeError, match="non-empty string"):
                ContainerCreateStatechart.sequence()
