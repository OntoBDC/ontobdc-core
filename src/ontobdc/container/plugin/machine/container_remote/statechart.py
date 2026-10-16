from typing import Any, ClassVar, Dict, List
from pathlib import Path

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.container.plugin.machine.container_remote.port import RemoteContainerProcessStatePort


class RemoteContainerStatechart:
    """Provide the statechart definition independently of machine execution."""

    PACKAGE: str = "ontobdc.container.plugin.machine.container_remote"
    FILE: str = "standard_container_remote.yaml"

    CAPABILITY_IDS: ClassVar[Dict[str, str]] = {
        "remote_file_available": (
            "org.ontobdc.container.plugin.capability.transformation.target."
            "remote_file_available"
        ),
        "remote_container_reachable": (
            "org.ontobdc.container.plugin.capability.transformation.target."
            "remote_container_reachable"
        ),
        "storage_root_recovered": (
            "org.ontobdc.cli.plugin.capability.transformation.target."
            "storage_root_recovered"
        ),
        "temp_storage_root_initialized": (
            "org.ontobdc.cli.plugin.capability.transformation.target."
            "temp_storage_root_initialized"
        ),
        "container_created": (
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_created"
        ),
        "container_files_downloaded": (
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_files_downloaded"
        ),
        "container_refreshed": (
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_refreshed"
        ),
    }

    @classmethod
    def path(cls) -> Path:
        return StatechartLocator.locate(cls.PACKAGE, cls.FILE)

    @classmethod
    def sequence(cls) -> List[str]:
        data: Any = yaml.safe_load(cls.path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Remote container statechart must be a mapping.")

        return StateWorkerAdapter.compute_state_sequence(data)

    @classmethod
    def capability_id(cls, state: RemoteContainerProcessStatePort) -> str:
        state_name: str = state.value.strip("_")
        capability_id: str = cls.CAPABILITY_IDS.get(state_name)
        if capability_id is None:
            raise ValueError(
                f"Remote container capability identifier not declared for state: {state.value}"
            )
        return capability_id

    @classmethod
    def is_terminal(cls, state: RemoteContainerProcessStatePort) -> bool:
        return state.value.strip("_") == cls.sequence()[-1]
