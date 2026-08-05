from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class ContainerAttachError(RuntimeError):
    state = ContainerAttachProcessState.UNDEFINED


class InvalidContainerPathError(ContainerAttachError):
    state = ContainerAttachProcessState.INVALID_CONTAINER_PATH


class InvalidContainerGraphError(ContainerAttachError):
    state = ContainerAttachProcessState.INVALID_CONTAINER_GRAPH


class IdentityConflictError(ContainerAttachError):
    state = ContainerAttachProcessState.IDENTITY_CONFLICT


class DatasetAttachError(ContainerAttachError):
    state = ContainerAttachProcessState.DATASET_ATTACH_FAILED


class StorageIndexAttachError(ContainerAttachError):
    state = ContainerAttachProcessState.STORAGE_INDEX_ATTACH_FAILED


class AttachRollbackError(ContainerAttachError):
    state = ContainerAttachProcessState.ATTACH_ROLLBACK_FAILED


def error_state_for_exception(
    error: Exception,
) -> ContainerAttachProcessState:
    if isinstance(error, ContainerAttachError):
        return error.state
    return ContainerAttachProcessState.INVALID_CONTAINER_GRAPH
