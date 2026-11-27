from typing import Any, ClassVar, Dict, List
from pathlib import Path

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.context.plugin.machine.action_dates_catalog.port import ActionDatesCatalogProcessStatePort


class ActionDatesCatalogStatechart:
    """Provide the statechart definition independently of machine execution."""

    PACKAGE: str = "ontobdc.context.plugin.machine.action_dates_catalog"
    FILE: str = "standard_action_dates_catalog.yaml"

    CAPABILITY_IDS: ClassVar[Dict[str, str]] = {
        "days_cataloged": (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "days_cataloged"
        ),
    }

    @classmethod
    def path(cls) -> Path:
        return StatechartLocator.locate(cls.PACKAGE, cls.FILE)

    @classmethod
    def sequence(cls) -> List[str]:
        data: Any = yaml.safe_load(cls.path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Action dates catalog statechart must be a mapping.")

        return StateWorkerAdapter.compute_state_sequence(data)

    @classmethod
    def capability_id(cls, state: ActionDatesCatalogProcessStatePort) -> str:
        state_name: str = state.value.strip("_")
        capability_id: str = cls.CAPABILITY_IDS.get(state_name)
        if capability_id is None:
            raise ValueError(
                f"Action dates catalog capability identifier not declared for state: {state.value}"
            )
        return capability_id

    @classmethod
    def is_terminal(cls, state: ActionDatesCatalogProcessStatePort) -> bool:
        return state.value.strip("_") == cls.sequence()[-1]
