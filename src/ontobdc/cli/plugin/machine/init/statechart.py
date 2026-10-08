from typing import Any, Dict, List
from pathlib import Path

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter


class CliInitStatechart:
    """Provide the statechart definition independently of machine execution."""

    PACKAGE: str = "ontobdc.cli.plugin.machine.init"
    FILE: str = "standard_init.yaml"

    @classmethod
    def path(cls) -> Path:
        return StatechartLocator.locate(cls.PACKAGE, cls.FILE)

    @classmethod
    def sequence(cls) -> List[str]:
        data: Any = yaml.safe_load(cls.path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("CLI init statechart must be a mapping.")

        return StateWorkerAdapter.compute_state_sequence(data)
