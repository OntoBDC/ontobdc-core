from pathlib import Path
from typing import Any, ClassVar, Dict, List

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.storage.plugin.machine.open_file.port import OpenFileProcessStatePort


class OpenFileStatechart:
    """Provide the open-file statechart definition independently of execution."""

    CAPABILITY_IDS: ClassVar[Dict[str, str]] = {
        "file_metadata_extracted": (
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted"
        ),
        "file_opening_strategy_found": (
            "org.ontobdc.storage.plugin.capability.transformation."
            "file_opening_strategy_found"
        ),
    }

    @staticmethod
    def path() -> Path:
        return StatechartLocator.locate(
            "ontobdc.storage.plugin.machine.open_file",
            "standard_open_file.yaml",
        )

    @classmethod
    def sequence(cls) -> List[str]:
        root_state: Dict[str, Any] = cls._data()["statechart"]["root state"]
        states_raw: Any = root_state.get("states")
        if not isinstance(states_raw, list):
            raise TypeError("Open-file statechart states must be a list.")

        states_by_name: Dict[str, Dict[str, Any]] = {
            state["name"]: state
            for state in states_raw
            if isinstance(state, dict) and isinstance(state.get("name"), str)
        }
        current_name: Any = root_state.get("initial")
        if not isinstance(current_name, str) or not current_name:
            raise TypeError("Open-file statechart initial state must be a string.")

        sequence: List[str] = [current_name]
        while "transitions" in states_by_name[current_name]:
            transitions: Any = states_by_name[current_name]["transitions"]
            if not isinstance(transitions, list) or len(transitions) != 1:
                raise ValueError(
                    "Open-file statechart must be linear after "
                    f"'{current_name}'."
                )

            transition: Any = transitions[0]
            if not isinstance(transition, dict):
                raise TypeError("Open-file statechart transition must be a mapping.")

            target: Any = transition.get("target")
            if not isinstance(target, str) or not target:
                raise TypeError(
                    "Open-file statechart target must be a non-empty string."
                )
            if target not in states_by_name:
                raise ValueError(
                    f"Open-file statechart target is not declared: '{target}'."
                )
            if target in sequence:
                raise ValueError(
                    f"Open-file statechart contains a cycle at '{target}'."
                )

            current_name = target
            sequence.append(current_name)

        return sequence

    @classmethod
    def capability_id(cls, state: OpenFileProcessStatePort) -> str:
        state_name = state.value.strip("_")
        capability_id = cls.CAPABILITY_IDS.get(state_name)
        if capability_id is None:
            raise ValueError(
                f"Open-file capability identifier not declared for state: {state.value}"
            )
        return capability_id

    @classmethod
    def is_terminal(cls, state: OpenFileProcessStatePort) -> bool:
        return state.value.strip("_") == cls.sequence()[-1]

    @classmethod
    def _data(cls) -> Dict[str, Any]:
        statechart_data: Any = yaml.safe_load(
            cls.path().read_text(encoding="utf-8")
        )
        if not isinstance(statechart_data, dict):
            raise TypeError("Open-file statechart must be a mapping.")
        return statechart_data
