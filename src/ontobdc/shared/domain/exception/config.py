class ContainerRootDirectoryNotSetError(FileNotFoundError):
    """
    Raised when the container root directory cannot be resolved.
    """
    default_message: str = "Container root directory not set."

    def __init__(self, message: str = "Container root directory not set."):
        super().__init__(message)
