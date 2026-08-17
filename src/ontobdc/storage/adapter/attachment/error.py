from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class ContainerAttachError(RuntimeError):
    state: ContainerAttachProcessState = ContainerAttachProcessState.UNDEFINED


class InvalidContainerPathError(ContainerAttachError):
    state: ContainerAttachProcessState = (
        ContainerAttachProcessState.INVALID_CONTAINER_PATH
    )


class InvalidContainerGraphError(ContainerAttachError):
    state: ContainerAttachProcessState = (
        ContainerAttachProcessState.INVALID_CONTAINER_GRAPH
    )


class IdentityConflictError(ContainerAttachError):
    state: ContainerAttachProcessState = (
        ContainerAttachProcessState.IDENTITY_CONFLICT
    )


class DatasetAttachError(ContainerAttachError):
    state: ContainerAttachProcessState = (
        ContainerAttachProcessState.DATASET_ATTACH_FAILED
    )


class StorageIndexAttachError(ContainerAttachError):
    state: ContainerAttachProcessState = (
        ContainerAttachProcessState.STORAGE_INDEX_ATTACH_FAILED
    )


class AttachRollbackError(ContainerAttachError):
    state: ContainerAttachProcessState = (
        ContainerAttachProcessState.ATTACH_ROLLBACK_FAILED
    )


class AttachmentErrorClassifier:
    """Map arbitrary exceptions to ``ContainerAttachProcessState`` values."""

    @classmethod
    def error_state_for_exception(
        cls,
        error: Exception,
    ) -> ContainerAttachProcessState:
        if isinstance(error, ContainerAttachError):
            return error.state
        return ContainerAttachProcessState.INVALID_CONTAINER_GRAPH
