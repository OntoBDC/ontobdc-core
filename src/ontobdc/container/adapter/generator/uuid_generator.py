from uuid import uuid4


class UuidGenerator:
    """
    ``facade:UuidGenerator``: a random universally unique identifier
    (RFC 4122, version 4), written as text.
    """

    @staticmethod
    def generate() -> str:
        return str(uuid4())
