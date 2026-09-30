from __future__ import annotations

import os
from abc import abstractmethod
import sys
from typing import Any, ClassVar, List, Optional, Set, Tuple, Type
import inspect
import pkgutil
import importlib

from ontobdc.shared.adapter.config import (
    ConfigDataAdapter,
    UnsetProjectRootConfigDataAdapter,
)
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextStrategyPort
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.port.loader import (
    CommandLoaderPort,
    PluginLoaderPort,
    ResolverLoaderPort,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.port.resolver import ParamResolverStrategyPort
from ontobdc.shared.domain.exception.config import (
    ProjectRootDirectoryNotSetError,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class PluginLoader(PluginLoaderPort):
    """
    Base plugin loader responsible for discovering and instantiating dynamic plugins across the application.
    """
    def _make_config_data_adapter(self) -> ConfigDataPort:
        try:
            return ConfigDataAdapter()

        except ProjectRootDirectoryNotSetError:
            pass

        return UnsetProjectRootConfigDataAdapter()

    def _walk_packages_recursive(self, path: List[str], prefix: str, current_depth: int, max_depth: int) -> List[Tuple[Any, str, bool]]:
        """
        Recursively walks through packages up to a maximum depth.
        Returns a list of tuples containing (importer, module_name, is_package).
        """
        results = []
        for importer, name, is_pkg in pkgutil.iter_modules(path, prefix):
            results.append((importer, name, is_pkg))
            if is_pkg and current_depth < max_depth:
                try:
                    # In python 3.10+, iter_modules path resolution is easiest using importlib
                    module = importlib.import_module(name)
                    if hasattr(module, "__path__"):
                        results.extend(self._walk_packages_recursive(module.__path__, name + ".", current_depth + 1, max_depth))
                except Exception as e:
                    # Do not print error if we can't walk deeper
                    pass
        return results
        
    def _scan_directory(self, resource: str, base_dir: str, base_pkg: str, discovered: List[str]) -> List[str]:
        try:
            for entry in sorted(os.listdir(base_dir)):
                if entry.startswith(".") or entry.startswith("_") or entry == "__pycache__":
                    continue
                entry_path = os.path.join(base_dir, entry)
                if not os.path.isdir(entry_path):
                    continue

                plugin_pkg_dir = os.path.join(entry_path, "plugin")
                resource_dir = os.path.join(plugin_pkg_dir, resource)

                if os.path.isdir(resource_dir):
                    discovered.append(f"{base_pkg}.{entry}.plugin")
        except Exception:
            pass

        return discovered

    def _list_plugin_folder(self, resource: str, root_package: str = "ontobdc") -> List[str]:
        discovered: List[str] = []

        if root_package == "ontobdc":
            try:
                ontobdc_root: str = str(self._make_config_data_adapter().script_dir)
                discovered = self._scan_directory(resource, ontobdc_root, "ontobdc", discovered)
                module_dir = os.path.join(ontobdc_root, "module")
                if os.path.isdir(module_dir):
                    discovered = self._scan_directory(resource, module_dir, "ontobdc.module", discovered)
            except Exception:
                return []

            return discovered

        # A downstream package (e.g. infobim) built on ontobdc's own plugin
        # convention (<domain>/plugin/<resource>/*.py) — resolved via the
        # installed-package lookup instead of ConfigDataAdapter.script_dir,
        # which is ontobdc-specific. No "module/" extension slot for these:
        # that convention only applies to ontobdc itself.
        try:
            package_root: Optional[str] = self._find_installed_package_root(root_package)
            if package_root is None:
                return []
            discovered = self._scan_directory(resource, package_root, root_package, discovered)
        except Exception:
            return []

        return discovered

    @staticmethod
    def _find_installed_package_root(package_name: str) -> Optional[str]:
        try:
            spec = importlib.util.find_spec(package_name)
        except (ImportError, ValueError):
            return None
        if spec is None or not spec.submodule_search_locations:
            return None
        return next(iter(spec.submodule_search_locations), None)

    @abstractmethod
    def get_all(self, resource: str) -> List[Type[PluginLoaderPort]]:
        """
        Retrieves all plugins of the specified resource type.
        """
        ...

    def get(self, resource: str, id: str) -> Type[PluginLoaderPort]:
        """
        Retrieves a specific plugin of the specified resource type by its ID.
        """
        for rsrc in self.get_all(resource):
            metadata: Any = getattr(rsrc, "METADATA", None)
            metadata_id: Any = getattr(metadata, "id", None)
            if isinstance(metadata_id, str) and metadata_id == id:
                return rsrc

        return None


class CapabilityLoader(PluginLoader):
    """
    Plugin loader specifically responsible for discovering and loading Capability plugins.
    """

    DEFAULT_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("ontobdc",)

    def __init__(
        self,
        root_packages: Tuple[str, ...] = DEFAULT_ROOT_PACKAGES,
    ) -> None:
        self._root_packages: Tuple[str, ...] = root_packages

    def get(self, id: str) -> Type[CapabilityPort]:
        """
        Retrieves a capability plugin by its unique ID.
        """
        return super().get("capability", id)

    def get_all(self, resource: str = "capability") -> List[Type[CapabilityPort]]:
        """
        Retrieves all available capability plugins discovered in the application's plugin folders.
        """
        capabilities: List[Type[CapabilityPort]] = []
        capability_ids: Set[str] = set()
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

            resource_pkg_name = f"{pkg_name}.{resource}"
            try:
                resource_package = importlib.import_module(resource_pkg_name)
            except ImportError:
                continue

            if not hasattr(resource_package, "__path__"):
                continue

            package_prefix = getattr(resource_package, "__name__", resource_pkg_name) + "."
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
                        except TypeError:
                            continue

                        metadata_obj: Any = getattr(obj, "METADATA", None)
                        if not isinstance(metadata_obj, CapabilityMetadata):
                            continue
                        if not metadata_obj.id:
                            continue

                        if metadata_obj.id in capability_ids:
                            continue

                        capabilities.append(obj)
                        capability_ids.add(metadata_obj.id)
                except Exception as e:
                    print(
                        f"[CapabilityLoader] Error loading module {name}: {e}",
                        file=sys.stderr,
                    )
                    continue

        return capabilities


class ResolverLoader(PluginLoader, ResolverLoaderPort):
    """
    Plugin loader responsible for discovering parameter resolver strategies.

    Discovery follows the same <domain>/plugin/<resource>/ convention every
    other loader in this module already uses, so a strategy is found by being
    shipped in the right package, never by matching a file name or a class
    name derived from the URI it happens to answer for.
    """

    def __init__(
        self,
        root_packages: Tuple[str, ...] = ("ontobdc",),
    ) -> None:
        self._root_packages: Tuple[str, ...] = root_packages

    def get_all(self, resource: str = "resolver") -> List[Type[ParamResolverStrategyPort]]:
        """
        Retrieves every parameter resolver strategy discovered in the plugin folders.
        """
        strategies: List[Type[ParamResolverStrategyPort]] = []
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
                        if not issubclass(obj, ParamResolverStrategyPort):
                            continue
                        if inspect.isabstract(obj) or obj is ParamResolverStrategyPort:
                            continue
                        if obj in strategies:
                            continue

                        strategies.append(obj)
                except Exception as error:
                    print(
                        f"[ResolverLoader] Error loading module {name}: {error}",
                        file=sys.stderr,
                    )
                    continue

        return strategies


class ParameterLoader(PluginLoader):
    """
    Plugin loader responsible for discovering and loading Parameter Strategy plugins.
    """

    def __init__(
        self,
        logger: Optional[LogRepositoryPort] = None,
        root_packages: Tuple[str, ...] = ("ontobdc",),
    ) -> None:
        try:
            from ontobdc.cli.adapter.logger import NullLogRepository as _NullLog
        except Exception:
            _NullLog = None  # type: ignore[misc,assignment]

        if logger is None and _NullLog is not None:
            logger = _NullLog()
        self._logger: Optional[LogRepositoryPort] = logger
        self._root_packages: Tuple[str, ...] = root_packages

    @property
    def root_packages(self) -> Tuple[str, ...]:
        """
        Return the packages this loader discovers strategies in.
        """
        return self._root_packages

    def get(self, id: str) -> CliContextStrategyPort:
        """
        Retrieves a parameter strategy plugin by its unique ID.
        """
        return super().get("parameter", id)

    def get_all(self, resource: str = "parameter") -> List[CliContextStrategyPort]:
        """
        Retrieves all available parameter strategy plugins discovered in the application.

        When a parameter strategy module fails to import (syntax error, missing
        dependency, broken ``METADATA`` declaration...) the loader used to
        swallow the exception silently and continue with the remaining
        candidates. That behaviour turned broken strategies invisible during
        development; the loader now emits a ``WARNING`` through its injected
        logger describing the offending module name and the original
        exception message so the operator can fix the plugin instead of
        wondering why a declared strategy never runs.
        """
        strategies: List[CliContextStrategyPort] = []
        strategy_ids: Set[str] = set()
        plugin_packages: List[str] = []
        root_package: str
        for root_package in self._root_packages:
            plugin_packages.extend(
                self._list_plugin_folder(resource, root_package)
            )

        for pkg_name in plugin_packages:
            try:
                package = importlib.import_module(pkg_name)
            except ImportError as import_error:
                if self._logger is not None:
                    self._logger.log_warning(
                        "ParameterLoader: skipping plugin domain package "
                        f"'{pkg_name}' (ImportError: {import_error})"
                    )
                continue

            if not hasattr(package, "__path__"):
                continue

            resource_pkg_name = f"{pkg_name}.{resource}"
            try:
                resource_package = importlib.import_module(resource_pkg_name)
            except ImportError as import_error:
                if self._logger is not None:
                    self._logger.log_warning(
                        "ParameterLoader: skipping resource package "
                        f"'{resource_pkg_name}' inside '{pkg_name}' "
                        f"(ImportError: {import_error})"
                    )
                continue

            if not hasattr(resource_package, "__path__"):
                continue

            package_prefix = getattr(resource_package, "__name__", resource_pkg_name) + "."
            for _, name, _ in self._walk_packages_recursive(resource_package.__path__, package_prefix, current_depth=1, max_depth=10):
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj)
                                and issubclass(obj, CliContextStrategyPort)
                                and obj is not CliContextStrategyPort):
                            strategy: CliContextStrategyPort = obj()
                            metadata: Any = getattr(strategy, "METADATA", None)
                            strategy_id: str = str(
                                getattr(metadata, "id", "") or ""
                            ).strip()
                            if strategy_id and strategy_id in strategy_ids:
                                continue
                            strategies.append(strategy)
                            if strategy_id:
                                strategy_ids.add(strategy_id)
                except Exception as exception:
                    if self._logger is not None:
                        self._logger.log_warning(
                            "ParameterLoader: discarding strategy module "
                            f"'{name}' — {type(exception).__name__}: {exception}"
                        )
                    continue

        return strategies


class CommandLoader(PluginLoader, CommandLoaderPort):
    """
    Command loader for plugin commands.
    """
    def __init__(self, logical_component: str, logger: LogRepositoryPort, root_package: str = "ontobdc"):
        self._logical_component: str = logical_component
        self._logger: LogRepositoryPort = logger
        self._root_package: str = root_package

    def get(self, id: str) -> Type[CliCommandPort]:
        """
        Retrieves a command plugin by its unique ID.
        """
        return super().get("command", id)

    def get_all(self, resource: str = "command") -> List[Type[CliCommandPort]]:
        """
        Retrieves all available command plugins mapped to the specified logical component.
        """
        commands: List[Type[CliCommandPort]] = []

        for pkg_name in [pkg for pkg in self._list_plugin_folder(resource, self._root_package) if pkg.split('.')[1] == self._logical_component]:
            try:
                package = importlib.import_module(pkg_name)
            except ImportError as e:
                self._logger.log_warning(f"Error loading module {pkg_name}: {e}")
                continue

            if not hasattr(package, "__path__"):
                continue

            resource_pkg_name = f"{pkg_name}.{resource}"

            try:
                resource_package = importlib.import_module(resource_pkg_name)
            except ImportError as e:
                self._logger.log_warning(f"Error loading module {resource_pkg_name}: {e}")
                continue

            if not hasattr(resource_package, "__path__"):
                continue

            package_prefix = getattr(resource_package, "__name__", resource_pkg_name) + "."
            for _, name, _ in self._walk_packages_recursive(resource_package.__path__, package_prefix, current_depth=1, max_depth=10):
                try:
                    module = importlib.import_module(name)
                    # Force evaluate module classes
                    for _, obj in inspect.getmembers(module):
                        if not (inspect.isclass(obj)
                                and issubclass(obj, CliCommandPort)
                                and obj is not CliCommandPort):
                            continue

                        command_metadata = getattr(obj, "METADATA", None)

                        if getattr(command_metadata, "logical_component", None) != self._logical_component:
                            continue

                        if obj not in commands:
                            commands.append(obj)
                except Exception as e:
                    self._logger.log_warning(f"{package_prefix}{name} raised the error: {e}")
                    continue

        return commands
