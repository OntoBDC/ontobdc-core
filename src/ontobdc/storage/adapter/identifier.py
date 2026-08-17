import uuid

CONTAINER_ID_PREFIX: str = "urn:uuid:"


def generate_container_id() -> str:
    """Mint a new, opaque, stable container identifier.

    Identity is decoupled from location on purpose: a container's id never
    changes for the container's lifetime, regardless of where it lives on
    disk. ``PROV.atLocation`` is the mutable pointer to that location.
    """
    return f"{CONTAINER_ID_PREFIX}{uuid.uuid4()}"


def is_valid_container_id(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(CONTAINER_ID_PREFIX):
        return False

    raw_uuid: str = value[len(CONTAINER_ID_PREFIX):]
    try:
        parsed: uuid.UUID = uuid.UUID(raw_uuid, version=4)
    except ValueError:
        return False

    return str(parsed) == raw_uuid


def normalize_container_id(value: str) -> str:
    """Expand a bare uuid4 (no ``urn:`` prefix) into its full container id form."""
    normalized: str = value.strip()
    if not normalized:
        raise ValueError("Container id cannot be empty.")
    if normalized.startswith("urn:"):
        return normalized
    return f"{CONTAINER_ID_PREFIX}{normalized}"
