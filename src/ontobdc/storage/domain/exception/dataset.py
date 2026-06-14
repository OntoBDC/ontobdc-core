


class DatasetIndexNotFoundException(Exception):
    """
    Exception for when the dataset index.ttl is not found.
    """
    IDENTIFIER = "org.ontobdc.domain.storage.exception.dataset.index_not_found"
    TITLE = "Dataset Index Not Found"

    def __init__(self, message: str):
        super().__init__(message)
