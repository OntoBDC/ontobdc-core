import pkgutil
import importlib
import inspect
import sys
from typing import List, Type
from ontobdc.run.core.capability import Capability
from ontobdc.run.core.action import Action

class CapabilityLoader:
    @staticmethod
    def load_from_package(package_name: str) -> List[Type[Capability]]:
        capabilities = []
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            return []

        if not hasattr(package, "__path__"):
            return []

        package_list: List[pkgutil.ModuleInfo] = list(pkgutil.walk_packages(package.__path__, package.__name__ + "."))
        package_list = [module_info for module_info in package_list if module_info.ispkg]
        package_list = [module_info for module_info in package_list if '/plugin' in module_info.module_finder.path]

        # Walk through all submodules
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(name)
                for _, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and hasattr(obj, "METADATA") and obj.METADATA and obj.METADATA.id:
                        if issubclass(obj, Capability):
                            capabilities.append(obj)
            except Exception as e:
                # Ignore modules that fail to import
                # import traceback
                print(f"[CapabilityLoader] Error loading module {name}: {e}", file=sys.stderr)
                # traceback.print_exc()
                continue

        return capabilities


class ActionLoader:
    @staticmethod
    def load_from_package(package_name: str) -> List[Type[Action]]:
        actions = []
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            return []

        if not hasattr(package, "__path__"):
            return []

        package_list: List[pkgutil.ModuleInfo] = list(pkgutil.walk_packages(package.__path__, package.__name__ + "."))
        package_list = [module_info for module_info in package_list if module_info.ispkg]
        package_list = [module_info for module_info in package_list if '/plugin' in module_info.module_finder.path]

        # Walk through all submodules
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(name)
                for _, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and hasattr(obj, "METADATA") and obj.METADATA and obj.METADATA.id:
                        if issubclass(obj, Action):
                            actions.append(obj)
            except Exception as e:
                # Ignore modules that fail to import
                # import traceback
                print(f"[ActionLoader] Error loading module {name}: {e}", file=sys.stderr)
                # traceback.print_exc()
                continue

        return actions
