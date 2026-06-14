
import re
import json
import uuid
import hashlib
import requests
from rdflib.term import _is_valid_uri


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
    parts = re.split(r'[-_]', to_snake_case(name))
    return "".join(part.capitalize() for part in parts)

def to_snake_case(name: str) -> str:
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', name)
    name = re.sub(r'[-\s]+', '_', name)
    return name.lower()

def to_camel_case(name: str) -> str:
    """Converts snake_case or kebab-case to camelCase."""
    parts = re.split(r'[-_]', name)
    return parts[0].lower() + ''.join(part.capitalize() for part in parts[1:])

def is_valid_url(url: str, require_reachable: bool = False) -> bool:
    if not isinstance(url, str) or not url:
        return False

    if not url.strip().startswith("http://") and not url.strip().startswith("https://"):
        return False

    if require_reachable:
        try:
            requests.head(url, timeout=5)
        except requests.exceptions.RequestException:
            return False

    return True

def is_valid_uri(uri: str) -> bool:
    if not is_valid_url(uri):
        return False

    if not _is_valid_uri(uri):
        return False

    try:
        import rfc3987
        if rfc3987.match(uri, rule="URI") is None:
            return False
    except ImportError:
        raise ImportError("rfc3987 is required to validate URIs")
    except Exception:
        return False

    return True

