class StorageObdcFileError(Exception):
    """
    Raised when an ``.obdc`` file cannot be read: it is not a zip archive,
    it holds no ``remote.ttl``, or its ``remote.ttl`` is not valid Turtle.
    """
