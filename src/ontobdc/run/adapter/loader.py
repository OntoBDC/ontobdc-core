import pkgutil
import importlib
import inspect
import os
import sys
from typing import List, Type
from ontobdc.core.domain.capability import Capability
from ontobdc.run.domain.action import Action

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
