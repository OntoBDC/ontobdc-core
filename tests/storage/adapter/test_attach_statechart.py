from pathlib import Path

import yaml

from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


def test_attach_statechart_matches_success_state_sequence() -> None:
    statechart_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ontobdc"
        / "storage"
        / "domain"
        / "machine"
        / "standard_container_attach.yaml"
    )
    data = yaml.safe_load(statechart_path.read_text(encoding="utf-8"))
    state_names = [
        state["name"]
        for state in data["statechart"]["root state"]["states"]
    ]

    for state in (
        ContainerAttachProcessState.UNDEFINED,
        ContainerAttachProcessState.CONTAINER_INSPECTED,
        ContainerAttachProcessState.IDENTITY_RESOLVED,
        ContainerAttachProcessState.CONTAINER_METADATA_ATTACHED,
        ContainerAttachProcessState.DATASETS_ATTACHED,
        ContainerAttachProcessState.STORAGE_INDEX_ATTACHED,
        ContainerAttachProcessState.CONTEXT_ATTACHED,
        ContainerAttachProcessState.CONTAINER_ATTACHED,
    ):
        assert state.value.strip("_") in state_names

    for error_state in (
        ContainerAttachProcessState.INVALID_CONTAINER_PATH,
        ContainerAttachProcessState.INVALID_CONTAINER_GRAPH,
        ContainerAttachProcessState.IDENTITY_CONFLICT,
        ContainerAttachProcessState.DATASET_ATTACH_FAILED,
        ContainerAttachProcessState.STORAGE_INDEX_ATTACH_FAILED,
        ContainerAttachProcessState.ATTACH_ROLLBACK_FAILED,
    ):
        assert error_state.value.strip("_") in state_names
