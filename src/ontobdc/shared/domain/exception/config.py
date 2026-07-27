


class ProjectRootDirectoryNotSetError(FileNotFoundError):
    """
    Raised when the project root directory cannot be resolved.
    """
    default_message: str = "Project root directory not set."

    def __init__(self, message: str = "Project root directory not set."):
        super().__init__(message)
