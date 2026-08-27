
import os
import sys
import pkgutil
import inspect
import importlib
import importlib.util
from abc import abstractmethod
from typing import Any, List, Optional, Set, Tuple, Type
from rdflib import Graph, URIRef
from rdflib.namespace import RDF
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.component import ComponentPort
from ontobdc.shared.domain.model.component import ComponentMetadata
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

    def __init__(
        self,
        root_packages: Tuple[str, ...] = ("ontobdc",),
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


class ComponentLoader(PluginLoader):
    """
    Plugin loader responsible for discovering presentation Components and
    matching them against entities in a data graph.

    Component descriptors are discovered both from this package's own
    view/plugin/component/ (via _list_plugin_folder, like every other
    plugin resource — <domain>/plugin/<resource>/) and directly from
    ontobdc_view's component/plugin/ (see _load_ontobdc_view_components).
    ontobdc_view inverts the last two segments deliberately — component/
    is the primary organizing concept there (plugin/ sits beside
    component/asset/, its JS counterpart) — which doesn't fit
    _list_plugin_folder's shared <pkg_name>.<resource> assembly (that
    assumes "plugin" wraps and the resource name is the final segment),
    so it's resolved as a one-off rather than forced through it.
    """

    def get(self, id: str) -> Type[ComponentPort]:
        """
        Retrieves a component plugin by its unique ID.
        """
        return super().get("component", id)

    def get_all(self, resource: str = "component") -> List[Type[ComponentPort]]:
        """
        Retrieves all available component plugins discovered in the application's plugin folders.
        """
        components: List[Type[ComponentPort]] = []
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

            components.extend(self._collect_components(resource_package))

        if resource == "component":
            components.extend(self._load_ontobdc_view_components())

        return components

    def _load_ontobdc_view_components(self) -> List[Type[ComponentPort]]:
        view_root = self._find_installed_package_root("ontobdc_view")
        if view_root is None:
            return []

        if not os.path.isdir(os.path.join(view_root, "component", "plugin")):
            return []

        try:
            resource_package = importlib.import_module("ontobdc_view.component.plugin")
        except ImportError:
            return []

        if not hasattr(resource_package, "__path__"):
            return []

        return self._collect_components(resource_package)

    def _collect_components(self, resource_package: Any) -> List[Type[ComponentPort]]:
        components: List[Type[ComponentPort]] = []
        package_prefix = getattr(resource_package, "__name__", "") + "."
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
                        if not issubclass(obj, ComponentPort) or obj is ComponentPort:
                            continue
                    except TypeError:
                        continue

                    metadata_obj: Any = getattr(obj, "METADATA", None)
                    if not isinstance(metadata_obj, ComponentMetadata):
                        continue

                    components.append(obj)
            except Exception as e:
                print(f"[ComponentLoader] Error loading module {name}: {e}", file=sys.stderr)
                continue

        return components

    def match(
        self,
        graph: Graph,
        entity: URIRef,
    ) -> List[Type[ComponentPort]]:
        """
        Resolve every discovered Content Tile component whose
        `required_uris` are all satisfied by `entity` in `graph`. Components
        with no `required_uris` are Chrome Tiles (see `match_tile_class`)
        and never match here, since matching them against an arbitrary
        entity would be vacuous.
        """
        matched: List[Type[ComponentPort]] = []
        for component_type in self.get_all():
            required_uris: List[str] = component_type.METADATA.required_uris
            if not required_uris:
                continue

            if all(
                self._entity_satisfies_uri(graph, entity, uri)
                for uri in required_uris
            ):
                matched.append(component_type)

        return matched

    def match_tile_class(self, tile_class: str) -> List[Type[ComponentPort]]:
        """
        Resolve every discovered Component that implements `tile_class` (a
        Tile subclass URI from the presentation ontology, e.g. `:LogoTile`).
        Used for Chrome Tile requests, which have no entity to infer a match
        from and must name the wanted class directly.
        """
        return [
            component_type
            for component_type in self.get_all()
            if component_type.METADATA.tile_class == tile_class
        ]

    @staticmethod
    def _entity_satisfies_uri(graph: Graph, entity: URIRef, uri: str) -> bool:
        term = URIRef(uri)
        if (entity, RDF.type, term) in graph:
            return True
        return any(predicate == term for predicate in graph.predicates(entity))


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
                        # A command module may import another domain's
                        # command class (e.g. to delegate/proxy to it) —
                        # that import makes it visible to inspect.getmembers
                        # too, but it belongs to ITS OWN declared domain, not
                        # whichever domain's directory this module happens to
                        # live under. Filtering on the class's own
                        # METADATA.logical_component (rather than the module
                        # path it was found via) keeps a domain's discovered
                        # command list scoped to commands that actually
                        # declare themselves as belonging to it — a plain
                        # re-export (`from ontobdc... import X`) still counts,
                        # since X's own METADATA is unchanged either way.
                        command_metadata = getattr(obj, "METADATA", None)
                        if getattr(command_metadata, "logical_component", None) != self._logical_component:
                            continue
                        if obj not in commands:
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
