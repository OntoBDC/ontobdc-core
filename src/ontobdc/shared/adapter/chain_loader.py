from __future__ import annotations

import importlib
import inspect
import sys
from typing import Any, ClassVar, List, Optional, Set, Tuple, Type

from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.adapter.loader import PluginLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort
from ontobdc.shared.domain.port.loader import ChainResponsibilityLoaderPort


class ChainResponsibilityLoader(
    PluginLoader,
    ChainResponsibilityLoaderPort,
):
    """
    Discover capabilities that support a chain responsibility contract.

    Responsibilities remain ordinary capability plugins under
    ``<domain>/plugin/capability``. A capability participates in a chain by
    implementing the concrete ``ChainResponsibilityPort`` requested by that
    chain; the chain does not own or enumerate capability classes itself.
    """

    DEFAULT_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("ontobdc",)

    def __init__(
        self,
        root_packages: Tuple[str, ...] = DEFAULT_ROOT_PACKAGES,
    ) -> None:
        self._root_packages: Tuple[str, ...] = root_packages

    def get(
        self,
        support: Type[ChainResponsibilityPort],
        id: str,
    ) -> Optional[Type[CapabilityPort]]:
        """
        Retrieve one capability supporting ``support`` by capability ID.
        """
        responsibility_type: Type[CapabilityPort]
        for responsibility_type in self.get_all(support):
            metadata: Any = getattr(responsibility_type, "METADATA", None)
            if isinstance(metadata, CapabilityMetadata) and metadata.id == id:
                return responsibility_type

        return None

    def get_all(
        self,
        support: Type[ChainResponsibilityPort],
        resource: str = "capability",
    ) -> List[Type[CapabilityPort]]:
        """
        Retrieve every capability that implements the requested support.
        """
        if not inspect.isclass(support):
            raise TypeError("Chain responsibility support must be a class.")
        if not issubclass(support, ChainResponsibilityPort):
            raise TypeError(
                "Chain responsibility support must implement "
                "ChainResponsibilityPort."
            )

        responsibilities: List[Type[CapabilityPort]] = []
        responsibility_ids: Set[str] = set()
        plugin_packages: List[str] = []

        root_package: str
        for root_package in self._root_packages:
            plugin_packages.extend(
                self._list_plugin_folder(resource, root_package)
            )

        for pkg_name in plugin_packages:
            try:
                package = importlib.import_module(pkg_name)
            except ImportError:
                continue

            if not hasattr(package, "__path__"):
                continue

            resource_pkg_name: str = f"{pkg_name}.{resource}"
            try:
                resource_package = importlib.import_module(resource_pkg_name)
            except ImportError:
                continue

            if not hasattr(resource_package, "__path__"):
                continue

            package_prefix: str = (
                getattr(resource_package, "__name__", resource_pkg_name) + "."
            )
            for _, name, _ in self._walk_packages_recursive(
                resource_package.__path__,
                package_prefix,
                current_depth=1,
                max_depth=10,
            ):
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module):
                        if not inspect.isclass(obj):
                            continue

                        try:
                            if not issubclass(obj, Capability):
                                continue
                            if not issubclass(obj, support):
                                continue
                        except TypeError:
                            continue

                        metadata: Any = getattr(obj, "METADATA", None)
                        if not isinstance(metadata, CapabilityMetadata):
                            continue
                        if not metadata.id:
                            continue
                        if metadata.id in responsibility_ids:
                            continue

                        responsibilities.append(obj)
                        responsibility_ids.add(metadata.id)
                except Exception as exc:
                    print(
                        f"[ChainResponsibilityLoader] Error loading module "
                        f"{name}: {exc}",
                        file=sys.stderr,
                    )
                    continue

        responsibilities.sort(
            key=lambda responsibility_type: responsibility_type.METADATA.id
        )
        return responsibilities
