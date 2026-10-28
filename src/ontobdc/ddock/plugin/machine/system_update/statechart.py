from typing import Any, Dict, List
from pathlib import Path

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.ddock.plugin.machine.system_update.state import (
    SystemUpdateProcessState,
)


class SystemUpdateStatechart:
    """Provide the statechart definition independently of machine execution."""

    @staticmethod
    def path() -> Path:
        return StatechartLocator.locate(
            "ontobdc.ddock.plugin.machine.system_update",
            "standard_system_update.yaml",
        )

    @classmethod
    def sequence(cls) -> List[str]:
        root_state: Dict[str, Any] = cls._data()["statechart"]["root state"]
        states_by_name: Dict[str, Dict[str, Any]] = {
            state["name"]: state for state in root_state["states"]
        }
        current_name: str = SystemUpdateProcessState.SYSTEM_DESCRIPTOR_VALID.value.strip("_")
        sequence: List[str] = [current_name]
        while "transitions" in states_by_name[current_name]:
            transitions: Any = states_by_name[current_name]["transitions"]
            if not isinstance(transitions, list) or len(transitions) != 1:
                raise ValueError(
                    "System update statechart must be linear after "
                    f"'{current_name}'."
                )

            transition: Any = transitions[0]
            if not isinstance(transition, dict):
                raise TypeError(
                    "System update statechart transition must be a mapping."
                )

            target: Any = transition["target"]
            if not isinstance(target, str) or not target:
                raise TypeError(
                    "System update statechart target must be a non-empty string."
                )
            if target in sequence:
                raise ValueError(
                    f"System update statechart contains a cycle at '{target}'."
                )

            current_name = target
            sequence.append(current_name)

        return sequence

    @classmethod
    def _data(cls) -> Dict[str, Any]:
        statechart_data: Any = yaml.safe_load(cls.path().read_text(encoding="utf-8"))
        if not isinstance(statechart_data, dict):
            raise TypeError("System update statechart must be a mapping.")

        return statechart_data
