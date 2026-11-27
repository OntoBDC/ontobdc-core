from typing import Any, ClassVar, Dict, List
from pathlib import Path

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.job.plugin.machine.job_create.port import JobCreateProcessStatePort


class JobCreateStatechart:
    """Provide the statechart definition independently of machine execution."""

    PACKAGE: str = "ontobdc.job.plugin.machine.job_create"
    FILE: str = "standard_job_create.yaml"

    CAPABILITY_IDS: ClassVar[Dict[str, str]] = {
        "graph_opened": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "graph_opened"
        ),
        "procedure_valid": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "procedure_valid"
        ),
        "target_located": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "target_located"
        ),
        "storage_hotfixed": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "storage_hotfixed"
        ),
        "container_hotfixed": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "container_hotfixed"
        ),
        "job_dataset_ready": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "job_dataset_ready"
        ),
        "job_created": (
            "org.ontobdc.job.plugin.capability.transformation.target."
            "job_created"
        ),
    }

    @classmethod
    def path(cls) -> Path:
        return StatechartLocator.locate(cls.PACKAGE, cls.FILE)

    @classmethod
    def sequence(cls) -> List[str]:
        data: Any = yaml.safe_load(cls.path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Job create statechart must be a mapping.")

        return StateWorkerAdapter.compute_state_sequence(data)

    @classmethod
    def capability_id(cls, state: JobCreateProcessStatePort) -> str:
        state_name: str = state.value.strip("_")
        capability_id: str = cls.CAPABILITY_IDS.get(state_name)
        if capability_id is None:
            raise ValueError(
                f"Job create capability identifier not declared for state: {state.value}"
            )
        return capability_id

    @classmethod
    def is_terminal(cls, state: JobCreateProcessStatePort) -> bool:
        return state.value.strip("_") == cls.sequence()[-1]
