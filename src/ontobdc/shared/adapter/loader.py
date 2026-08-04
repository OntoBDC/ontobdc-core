
import os
import sys
import pkgutil
import inspect
import importlib
from abc import abstractmethod
from typing import List, Optional, Tuple, Type, Any
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextStrategyPort
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError
from ontobdc.shared.domain.port.loader import CommandLoaderPort, PluginLoaderPort
from ontobdc.shared.adapter.config import ConfigDataAdapter, UnsetProjectRootConfigDataAdapter


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

    def _list_plugin_folder(self, resource: str) -> List[str]:
        discovered: List[str] = []
        ontobdc_root: str = str(self._make_config_data_adapter().script_dir)
        
        try:
            discovered = self._scan_directory(resource, ontobdc_root, "ontobdc", discovered)
            module_dir = os.path.join(ontobdc_root, "module")
            if os.path.isdir(module_dir):
                discovered = self._scan_directory(resource, module_dir, "ontobdc.module", discovered)
        except Exception:
            return []

        return discovered

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
        for pkg_name in self._list_plugin_folder(resource):
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

                        capabilities.append(obj)
                except Exception as e:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    log_script = os.path.join(current_dir, "..", "..", "cli", "print_log.sh")
                    if os.path.exists(log_script):
                        import subprocess
                        subprocess.run(
                            [sys.executable, log_script, "WARNING", f"Error loading module {name}: {e}"],
                            check=False,
                            stdout=sys.stderr,
                            stderr=sys.stderr,
                        )
                    else:
                        print(f"[CapabilityLoader] Error loading module {name}: {e}", file=sys.stderr)
                    continue

        return capabilities


class ParameterLoader(PluginLoader):
    """
    Plugin loader responsible for discovering and loading Parameter Strategy plugins.
    """
    def get(self, id: str) -> Type[CliContextStrategyPort]:
        """
        Retrieves a parameter strategy plugin by its unique ID.
        """
        return super().get("parameter", id)

    def get_all(self, resource: str = "parameter") -> List[Type[CliContextStrategyPort]]:
        """
        Retrieves all available parameter strategy plugins discovered in the application.
        """
        strategies: List[Type[CliContextStrategyPort]] = []
        for pkg_name in self._list_plugin_folder(resource):
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
            for _, name, _ in self._walk_packages_recursive(resource_package.__path__, package_prefix, current_depth=1, max_depth=10):
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj)
                                and issubclass(obj, CliContextStrategyPort)
                                and obj is not CliContextStrategyPort):
                            strategies.append(obj())
                except Exception as e:
                    # print(name)
                    # print(e)
                    continue

        return strategies


class CommandLoader(PluginLoader, CommandLoaderPort):
    """
    Command loader for plugin commands.
    """
    def __init__(self, logical_component: str, logger: LogRepositoryPort):
        self._logical_component: str = logical_component
        self._logger: LogRepositoryPort = logger

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

        for pkg_name in [pkg for pkg in self._list_plugin_folder(resource) if pkg.split('.')[1] == self._logical_component]:
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
                        if (inspect.isclass(obj)
                                and issubclass(obj, CliCommandPort)
                                and obj is not CliCommandPort):
                            commands.append(obj)
                except Exception as e:
                    self._logger.log_warning(f"{package_prefix}{name} raised the error: {e}")
                    continue

        return commands

class CheckLoader(PluginLoader):
    """
    Check loader for plugin checks.
    """
    def __init__(self, logger: LogRepositoryPort):
        self._logger: LogRepositoryPort = logger

    def get_all(self, resource: str = "check") -> List[Tuple[object, object]]:
        """
        Retrieves all check and hotfix modules as a list of tuples.
        """
        checks: List[Tuple[object, object]] = []

        for pkg_name in self._list_plugin_folder(resource):
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
            for _, name, is_pkg in self._walk_packages_recursive(resource_package.__path__, package_prefix, current_depth=1, max_depth=10):
                if not is_pkg:
                    continue

                check_module_name = f"{name}.check"
                hotfix_module_name = f"{name}.hotfix"
                try:
                    check_module = importlib.import_module(check_module_name)
                    if not hasattr(check_module, "main"):
                        continue

                    hotfix_module = None
                    try:
                        hotfix_module = importlib.import_module(hotfix_module_name)
                    except ImportError:
                        hotfix_module = None

                    checks.append((check_module, hotfix_module))
                except Exception as e:
                    self._logger.log_warning(f"{package_prefix}{name} raised the error: {e}")
                    continue

        self._logger.log_info(f"Loaded {len(checks)} check plugins")

        return checks

    def get(self, resource: str = "check", id: str = "") -> Optional[Tuple[object, object]]:
        """
        Retrieves a specific check and its corresponding hotfix module by its ID.
        """
        if not id:
            return None

        normalized_id = id.replace("-", "_")
        for check_module, hotfix_module in self.get_all(resource):
            module_name = getattr(check_module, "__name__", "")
            plugin_id = module_name.split(".")[-2] if "." in module_name else module_name
            if plugin_id == normalized_id:
                return (check_module, hotfix_module)

        return None
