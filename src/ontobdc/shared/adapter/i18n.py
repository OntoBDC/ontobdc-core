
from functools import lru_cache
from importlib.resources import files
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Tuple, Union

import yaml


LocaleCatalog = Dict[str, Dict[str, str]]
FullCatalog = Dict[str, LocaleCatalog]
LanguageEntry = Dict[str, str]


class I18nCatalogLoader:
    """Parametrizable loader for locale YAML files of one Python package.

    The owning package keeps its own ``i18n/locale/<locale>.yaml`` files, and
    this adapter encapsulates the otherwise-duplicated YAML loading, LRU
    caching and optional ``common`` namespace merging used across multiple
    top-level packages of the monorepo.
    """

    DEFAULT_LOCALE: ClassVar[str] = "en"
    DEFAULT_SUPPORTED_LOCALES: ClassVar[Tuple[str, ...]] = (
        "en",
        "pt-BR",
        "pt-PT",
        "es",
    )
    DEFAULT_RESOURCE_PATH: ClassVar[Tuple[str, ...]] = ("i18n", "locale")

    def __init__(
        self,
        package_name: str,
        supported_locales: Optional[Sequence[str]] = None,
        language_catalog: Optional[List[LanguageEntry]] = None,
        merge_common_namespace: bool = False,
        fallback_namespace: Optional[str] = None,
        resource_path: Optional[Sequence[str]] = None,
    ) -> None:
        if language_catalog and supported_locales is None:
            derived_locales: List[str] = [
                language["code"]
                for language in language_catalog
            ]
            supported_locales = derived_locales
        self._package_name: str = package_name
        self._language_catalog: Optional[List[LanguageEntry]] = language_catalog
        self._supported_locales: Tuple[str, ...] = tuple(
            supported_locales
            if supported_locales is not None
            else self.DEFAULT_SUPPORTED_LOCALES
        )
        self._merge_common_namespace: bool = merge_common_namespace
        self._fallback_namespace: Optional[str] = fallback_namespace
        self._resource_path: Tuple[str, ...] = tuple(
            resource_path if resource_path is not None else self.DEFAULT_RESOURCE_PATH
        )

    @property
    def supported_locales(self) -> Tuple[str, ...]:
        return self._supported_locales

    @property
    def language_catalog(self) -> Optional[List[LanguageEntry]]:
        return self._language_catalog

    def full_catalog(self) -> FullCatalog:
        """Return the memoized ``{locale: {namespace: {key: value}}}`` mapping.

        Uses chained, single-segment ``joinpath`` calls because
        ``importlib.resources.files(package)`` can be a ``MultiplexedPath``
        (e.g. an editable install), whose ``joinpath`` only accepts one
        segment at a time.
        """
        return self._cached_full_catalog()

    def catalog_for_namespace(self, namespace: str) -> LocaleCatalog:
        """Return ``{locale: {key: value}}`` for one namespace.

        If ``merge_common_namespace`` was enabled for this loader, each
        locale's dict starts with the ``common`` namespace contents and is
        then updated with the requested namespace. If the requested namespace
        does not exist and a ``fallback_namespace`` was set, the fallback is
        returned instead of an empty dict.
        """
        catalog: FullCatalog = self.full_catalog()
        result: LocaleCatalog = {}
        for locale in self._supported_locales:
            locale_catalog: Dict[str, Dict[str, str]] = catalog.get(locale, {})
            if self._merge_common_namespace:
                merged: Dict[str, str] = dict(locale_catalog.get("common", {}))
                merged.update(locale_catalog.get(namespace, {}))
                if not merged and self._fallback_namespace is not None:
                    merged = dict(locale_catalog.get(self._fallback_namespace, {}))
                result[locale] = merged
            else:
                payload: Dict[str, str] = dict(
                    locale_catalog.get(namespace, {})
                )
                if not payload and self._fallback_namespace is not None:
                    payload = dict(
                        locale_catalog.get(self._fallback_namespace, {})
                    )
                result[locale] = payload
        return result

    @lru_cache(maxsize=1)
    def _cached_full_catalog(self) -> FullCatalog:
        catalog: FullCatalog = {}
        locale_root: Any = files(self._package_name)
        for segment in self._resource_path:
            locale_root = locale_root.joinpath(segment)
        for locale in self._supported_locales:
            text: str = locale_root.joinpath(f"{locale}.yaml").read_text(
                encoding="utf-8",
            )
            catalog[locale] = yaml.safe_load(text) or {}
        return catalog
