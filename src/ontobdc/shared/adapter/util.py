
import re
import json
import uuid
import hashlib
import requests
import unicodedata
from functools import lru_cache
from typing import List, Callable
from rdflib.term import _is_valid_uri


def is_valid_uuid4(u):
    """
    Checks if a string is a valid UUID version 4.
    """
    try:
        val = uuid.UUID(u, version=4)
    except ValueError:
        return False

    return str(val) == u

def generate_hash(data: dict) -> str:
    """
    Generates a SHA-256 hash for a given dictionary.
    """
    raw = json.dumps(data, sort_keys=True, default=str).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()

def to_pascal_case(name):
    """Converts snake_case or kebab-case to PascalCase."""
    # Handle potential separators and capitalize parts
    parts = re.split(r'[-_]', to_snake_case(name))
    return "".join(part.capitalize() for part in parts)

def to_snake_case(name: str) -> str:
    """Converts a PascalCase, camelCase, or kebab-case string to snake_case."""
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', name)
    name = re.sub(r'[-\s]+', '_', name)
    return name.lower()

def to_camel_case(name: str) -> str:
    """Converts snake_case or kebab-case to camelCase."""
    parts = re.split(r'[-_]', name)
    return parts[0].lower() + ''.join(part.capitalize() for part in parts[1:])

def is_valid_url(url: str, require_reachable: bool = False) -> bool:
    """
    Checks if a string is a valid HTTP/HTTPS URL and optionally checks reachability.
    """
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
    """
    Checks if a string is a valid URI according to RFC 3987 and RDFLib specifications.
    """
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

def to_lemma(value: str, language: str = "en") -> str:
    normalized_value: str = unicodedata.normalize("NFKD", str(value or "").strip())
    ascii_value: str = normalized_value.encode("ascii", "ignore").decode("ascii")
    lowercase_value: str = ascii_value.lower()
    lowercase_value = re.sub(r"\be[-\s]+mail\b", "email", lowercase_value)
    tokenized_value: str = re.sub(r"[^a-z0-9]+", " ", lowercase_value).strip()
    token_list: List[str] = [
        lemmatize_token(token, language=language)
        for token in tokenized_value.split()
        if token
    ]
    return " ".join(token_list).strip()


def lemmatize_token(token: str, language: str = "en") -> str:
    normalized_token: str = str(token or "").strip()
    if not normalized_token:
        return ""

    spacy_language = _get_spacy_language(language)
    document = spacy_language(normalized_token)
    if len(document) == 0:
        return normalized_token.lower()

    lemma_value: str = str(document[0].lemma_ or "").strip().lower()
    if lemma_value:
        return lemma_value

    return normalized_token.lower()


@lru_cache(maxsize=8)
def _get_spacy_language(language: str):
    try:
        import spacy
    except ImportError as exc:
        raise ValueError("The 'spacy' package is required to lemmatize tokens.") from exc

    normalized_language: str = str(language or "en").lower().split("-", 1)[0].split("_", 1)[0]

    try:
        nlp = spacy.blank(normalized_language)
    except Exception as exc:
        raise ValueError(f"Unsupported spaCy language code '{normalized_language}'.") from exc

    if "lemmatizer" not in nlp.pipe_names:
        try:
            nlp.add_pipe("lemmatizer", config={"mode": "lookup"})
        except Exception as exc:
            raise ValueError(
                f"Could not configure spaCy lemmatizer for language '{normalized_language}'."
            ) from exc

    try:
        nlp.initialize()
    except Exception as exc:
        raise ValueError(
            f"Could not initialize spaCy lemmatizer for language '{normalized_language}'."
        ) from exc

    return nlp


class CapturingPrintLog:
    """
    Callable class to capture print_log messages while forwarding to original print_log.
    This class is picklable because it stores only simple references.
    """
    __slots__ = ['_original_print_log', '_error_messages', '_all_messages']

    def __init__(self, original_print_log: Callable, error_messages: List = None, all_messages: List = None):
        self._original_print_log = original_print_log
        self._error_messages = error_messages if error_messages is not None else []
        self._all_messages = all_messages if all_messages is not None else []

    def __call__(self, level: str, context: str, message: str):
        if self._original_print_log:
            self._original_print_log(level, context, message)
        if level.upper() in ["ERROR", "WARN", "WARNING"]:
            self._error_messages.append({'level': level, 'context': context, 'message': message})
        self._all_messages.append({'level': level, 'context': context, 'message': message})
