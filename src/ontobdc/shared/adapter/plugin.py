
import os
import sys
import pkgutil
import inspect
import importlib
from abc import abstractmethod
from typing import List, Optional, Tuple, Type
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.resource.capability import Capability
from ontobdc.shared.domain.port.resource import PluginResourcePort
from ontobdc.shared.domain.port.context import CliContextStrategyPort


class PluginResource(PluginResourcePort):
    def _list_plugin_folder(self, resource: str) -> List[str]:
        discovered: List[str] = []
        ontobdc_root: str = str(ConfigDataAdapter().script_dir)
        
        def scan_directory(base_dir: str, base_pkg: str):
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
        
        try:
            scan_directory(ontobdc_root, "ontobdc")
            module_dir = os.path.join(ontobdc_root, "module")
            if os.path.isdir(module_dir):
                scan_directory(module_dir, "ontobdc.module")
        except Exception:
            return []

        return discovered

    @abstractmethod
    def get_all(self, resource: str) -> List[Type[PluginResourcePort]]:
        ...

    def get(self, resource: str, id: str) -> Type[PluginResourcePort]:
        for rsrc in self.get_all(resource):
            if getattr(rsrc, "METADATA", None) and getattr(rsrc.METADATA, "id") and rsrc.METADATA.id == id:
                return rsrc

        return None


class CapabilityLoader(PluginResource):
    def get(self, id: str) -> Type[CapabilityPort]:
        return super().get("capability", id)

    def get_all(self, resource: str = "capability") -> List[Type[CapabilityPort]]:
        capabilities: List[Type[CapabilityPort]] = []
        for pkg_name in self._list_plugin_folder(resource):
            try:
                package = importlib.import_module(pkg_name)
            except ImportError:
                continue

            if not hasattr(package, "__path__"):
                continue

            for _, name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and hasattr(obj, "METADATA") and obj.METADATA and obj.METADATA.id:
                            if issubclass(obj, Capability):
                                capabilities.append(obj)
                except Exception as e:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    log_script = os.path.join(current_dir, "..", "..", "cli", "print_log.sh")
                    if os.path.exists(log_script):
                        import subprocess
                        subprocess.run(
                            ["bash", log_script, "WARNING", f"Error loading module {name}: {e}"],
                            check=False,
                            stdout=sys.stderr,
                            stderr=sys.stderr,
                        )
                    else:
                        print(f"[CapabilityLoader] Error loading module {name}: {e}", file=sys.stderr)
                    continue

        return capabilities


class ParameterLoader(PluginResource):
    def get(self, id: str) -> Type[CliContextStrategyPort]:
        return super().get("parameter", id)

    def get_all(self, resource: str = "parameter") -> List[Type[CliContextStrategyPort]]:
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
            for _, name, _ in pkgutil.walk_packages(resource_package.__path__, package_prefix):
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


class CommandLoader(PluginResource):
    """
    Command loader for plugin commands.
    """
    def __init__(self, logical_component: str, print_log: callable = None):
        self._logical_component: str = logical_component
        self._print_log: callable = print_log
        self._root_dir: str = ConfigDataAdapter().root_dir

    def get(self, id: str) -> Type[CliCommandPort]:
        return super().get("command", id)

    def get_all(self, resource: str = "command") -> List[Type[CliCommandPort]]:
        commands: List[Type[CliCommandPort]] = []

        for pkg_name in [pkg for pkg in self._list_plugin_folder(resource) if pkg.split('.')[1] == self._logical_component]:
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
            for _, name, _ in pkgutil.walk_packages(resource_package.__path__, package_prefix):
                try:
                    module = importlib.import_module(name)

                    for _, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj)
                                and issubclass(obj, CliCommandPort)
                                and obj is not CliCommandPort):
                            commands.append(obj)
                except Exception as e:
                    if self._print_log:
                        self._print_log('WARN', "Loading Module", f"{package_prefix}{name} raised the error: {e}")
                    continue

        return commands


class CheckLoader(PluginResource):
    """
    Check loader for plugin checks.
    """
    def __init__(self, print_log: callable = None):
        self._print_log: callable = print_log

    def get_all(self, resource: str = "check") -> List[Tuple[object, object]]:
        checks: List[Tuple[object, object]] = []

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
            for _, name, is_pkg in pkgutil.walk_packages(resource_package.__path__, package_prefix):
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
                except Exception:
                    continue

        return checks

    def get(self, resource: str = "check", id: str = "") -> Optional[Tuple[object, object]]:
        if not id:
            return None

        normalized_id = id.replace("-", "_")
        for check_module, hotfix_module in self.get_all(resource):
            module_name = getattr(check_module, "__name__", "")
            plugin_id = module_name.split(".")[-2] if "." in module_name else module_name
            if plugin_id == normalized_id:
                return (check_module, hotfix_module)

        return None
