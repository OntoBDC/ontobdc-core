
import re
import json
import uuid
import hashlib


def is_valid_uuid4(u):
    try:
        val = uuid.UUID(u, version=4)
    except ValueError:
        return False

    return str(val) == u

def generate_hash(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, default=str).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()

def to_pascal_case(name):
    """Converts snake_case or kebab-case to PascalCase."""
    # Handle potential separators and capitalize parts
    parts = re.split(r'[-_]', name)
    return "".join(part.capitalize() for part in parts)