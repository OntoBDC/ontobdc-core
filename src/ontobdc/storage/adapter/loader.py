import sys
import inspect
import importlib
from typing import List, Tuple, Type

from ontobdc.shared.adapter.loader import PluginLoader
from ontobdc.storage.domain.port.loader import FileTypificationLoaderPort
from ontobdc.storage.domain.port.typification import FileTypificationStrategyPort


class FileTypificationLoader(PluginLoader, FileTypificationLoaderPort):
    """
    Plugin loader responsible for discovering file typification strategies.

    Discovery follows the same <domain>/plugin/<resource>/ convention every
    other loader already uses, so a strategy is found by being shipped in
    the right package, never by matching a file name or a class name
    derived from the file family it happens to type.
    """

    def __init__(
        self,
        root_packages: Tuple[str, ...] = ("ontobdc",),
    ) -> None:
        self._root_packages: Tuple[str, ...] = root_packages

    def get_all(self, resource: str = "typification") -> List[Type[FileTypificationStrategyPort]]:
        """
        Retrieves every file typification strategy discovered in the plugin folders.
        """
        strategies: List[Type[FileTypificationStrategyPort]] = []
        plugin_packages: List[str] = []
        root_package: str
        for root_package in self._root_packages:
            plugin_packages.extend(
                self._list_plugin_folder(resource, root_package)
            )

        for pkg_name in plugin_packages:
            resource_pkg_name: str = f"{pkg_name}.{resource}"
            try:
                resource_package = importlib.import_module(resource_pkg_name)
            except ImportError:
                continue

            if not hasattr(resource_package, "__path__"):
                continue

            package_prefix: str = getattr(resource_package, "__name__", resource_pkg_name) + "."
            for _, name, _ in self._walk_packages_recursive(
                resource_package.__path__,
                package_prefix,
                current_depth=1,
                max_depth=10,
            ):
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if not issubclass(obj, FileTypificationStrategyPort):
                            continue
                        if inspect.isabstract(obj) or obj is FileTypificationStrategyPort:
                            continue
                        if obj in strategies:
                            continue

                        strategies.append(obj)
                except Exception as error:
                    print(
                        f"[FileTypificationLoader] Error loading module {name}: {error}",
                        file=sys.stderr,
                    )
                    continue

        return strategies
