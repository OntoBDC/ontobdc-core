from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Dict

import yaml

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ["en", "pt-BR", "pt-PT", "es"]


@lru_cache(maxsize=1)
def full_catalog() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Load and merge every locale YAML file into `{locale: {namespace: {key: value}}}`."""
    catalog: Dict[str, Dict[str, Dict[str, str]]] = {}
    # Chained, single-segment joinpath() calls — files("ontobdc") can be a
    # MultiplexedPath (e.g. an editable install), whose joinpath() only
    # accepts one segment at a time, unlike a plain pathlib.Path.
    locale_root = files("ontobdc").joinpath("i18n").joinpath("locale")
    for locale in SUPPORTED_LOCALES:
        text = locale_root.joinpath(f"{locale}.yaml").read_text(encoding="utf-8")
        catalog[locale] = yaml.safe_load(text) or {}
    return catalog


def catalog_for_namespace(namespace: str) -> Dict[str, Dict[str, str]]:
    """Return `{locale: {key: value}}` for one namespace."""
    catalog = full_catalog()
    result: Dict[str, Dict[str, str]] = {}
    for locale in SUPPORTED_LOCALES:
        result[locale] = dict(catalog.get(locale, {}).get(namespace, {}))
    return result
