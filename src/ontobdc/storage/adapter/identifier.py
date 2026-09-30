import uuid
from typing import ClassVar


class ContainerIdentifier:
    """
    Mints, validates and normalizes the identifier of a container.

    Identity is decoupled from location on purpose: a container's id never
    changes for the container's lifetime, regardless of where it lives on
    disk. ``PROV.atLocation`` is the mutable pointer to that location.
    """
    PREFIX: ClassVar[str] = "urn:uuid:"

    @classmethod
    def generate(cls) -> str:
        """
        Mint a new, opaque, stable container identifier.
        """
        return f"{cls.PREFIX}{uuid.uuid4()}"

    @classmethod
    def is_valid(cls, value: object) -> bool:
        """
        Return True when the value is a well formed container identifier.
        """
        if not isinstance(value, str) or not value.startswith(cls.PREFIX):
            return False

        raw_uuid: str = value[len(cls.PREFIX):]
        try:
            parsed: uuid.UUID = uuid.UUID(raw_uuid, version=4)
        except ValueError:
            return False

        return str(parsed) == raw_uuid

    @classmethod
    def normalize(cls, value: str) -> str:
        """
        Expand a bare uuid4, with no ``urn:`` prefix, into a container id.
        """
        normalized: str = value.strip()
        if not normalized:
            raise ValueError("Container id cannot be empty.")
        if normalized.startswith("urn:"):
            return normalized

        return f"{cls.PREFIX}{normalized}"
