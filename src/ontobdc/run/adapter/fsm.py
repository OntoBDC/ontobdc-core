import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, ClassVar, List, Optional, Tuple, Type

from ontobdc.shared.adapter.addon_package import AddonPackage
from ontobdc.shared.adapter.loader import PluginLoader


class FsmHandlerLocator:
    """
    Find the handler that runs the statechart in a YAML file.

    The handler is found by the layout of the folder, not by anything the
    YAML says: a machine is a package whose statechart sits beside a
    ``machine.py``, and that module defines the one
    ``*StateTransitionHandler`` class that drives it. The YAML is given as a
    path, or as a path inside an installed top-level package
    (``ontobdc/annotate/.../standard_x.yaml``), which is how a caller that
    does not know where the packages are installed names it.
    """

    MACHINE_MODULE: ClassVar[str] = "machine"
    HANDLER_SUFFIX: ClassVar[str] = "StateTransitionHandler"

    @classmethod
    def locate(cls, fsm: str) -> Tuple[Path, Type[Any]]:
        """
        The statechart file and the handler class of the machine it belongs to.

        Raises:
            FileNotFoundError: the YAML is nowhere to be found.
            LookupError: the folder holds no machine, or more than one handler.
            ValueError: the YAML is not the statechart of the handler beside it.
        """
        statechart: Path = cls._statechart(fsm)
        package: str = cls._package_of(statechart.parent)
        machine: Any = importlib.import_module(f"{package}.{cls.MACHINE_MODULE}")
        handlers: List[Type[Any]] = [
            member
            for name, member in inspect.getmembers(machine, inspect.isclass)
            if name.endswith(cls.HANDLER_SUFFIX)
            and member.__module__ == machine.__name__
            and callable(getattr(member, "execute", None))
        ]
        if len(handlers) != 1:
            raise LookupError(
                f"{package}.{cls.MACHINE_MODULE} defines {len(handlers)} "
                f"*{cls.HANDLER_SUFFIX} classes; a machine has exactly one."
            )

        declared: List[str] = sorted(
            {
                member.STATECHART_FILE
                for _, member in inspect.getmembers(machine, inspect.isclass)
                if member.__module__ == machine.__name__
                and isinstance(getattr(member, "STATECHART_FILE", None), str)
            }
        )
        if declared and statechart.name not in declared:
            raise ValueError(
                f"{statechart.name} is not the statechart of {handlers[0].__name__}: "
                f"it runs {', '.join(declared)}."
            )
        return statechart, handlers[0]

    @classmethod
    def _statechart(cls, fsm: str) -> Path:
        path: Path = Path(fsm).expanduser()
        if path.is_file():
            return path.resolve()
        if not path.is_absolute():
            for entry in sys.path:
                candidate: Path = Path(entry or ".") / path
                if candidate.is_file():
                    return candidate.resolve()
        raise FileNotFoundError(f"{fsm} is not a statechart file.")

    @classmethod
    def _package_of(cls, directory: Path) -> str:
        """
        The dotted name of the package the folder is, relative to the
        ``sys.path`` entry that holds it, or relative to the addon registered that holds it.
        """
        addon: Optional[str] = AddonPackage.package_of(directory)
        if addon is not None:
            return addon

        best: Optional[Path] = None
        for entry in sys.path:
            root: Path = Path(entry or ".").resolve()
            if root in (directory, *directory.parents) and (
                best is None or len(root.parts) > len(best.parts)
            ):
                best = root
        if best is None or best == directory:
            raise LookupError(f"{directory} is not inside an importable package.")
        return ".".join(directory.relative_to(best).parts)


class FsmIdLocator(PluginLoader):
    """
    Find a finite state machine by its id, in every plugin of every module.

    The id of a machine follows the pattern of the ids of the capabilities: ``org.`` and the dotted
    name of its package (``org.ontobdc.context.plugin.machine.action_dates_catalog``). A machine is a
    folder of ``<module>/plugin/machine`` that holds a ``machine.py`` and the YAML of its statechart.
    The machine is found by the layout of the folders, before anything is imported.
    """

    DEFAULT_ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("ontobdc",)
    RESOURCE: ClassVar[str] = "machine"

    def __init__(self, root_packages: Tuple[str, ...] = DEFAULT_ROOT_PACKAGES) -> None:
        self._root_packages: Tuple[str, ...] = root_packages

    def locate(self, fsm_id: str) -> Optional[Tuple[Path, Type[Any]]]:
        """
        The statechart file and the handler class of the machine with the id; None when no machine has it.

        Raises:
            LookupError: the folder of the machine holds no statechart, or more than one.
        """
        machine_id: str
        machine_directory: Path
        for machine_id, machine_directory in self.machines():
            if machine_id == fsm_id:
                return FsmHandlerLocator.locate(str(self._statechart(machine_directory)))

        return None

    def get_all(self, resource: str = "machine") -> List[Type[Any]]:
        """
        The handler class of every machine of every plugin.
        """
        return [
            FsmHandlerLocator.locate(str(self._statechart(machine_directory)))[1]
            for _, machine_directory in self.machines()
        ]

    def machines(self) -> List[Tuple[str, Path]]:
        """
        The id and the folder of every machine of every plugin: a folder of ``<module>/plugin/machine``
        that holds a ``machine.py``.
        """
        found: List[Tuple[str, Path]] = []
        root_package: str
        for root_package in self._root_packages:
            plugin_package: str
            for plugin_package in self._list_plugin_folder(self.RESOURCE, root_package):
                directory: Optional[Path] = self._machines_directory(root_package, plugin_package)
                if directory is None:
                    continue

                machine_directory: Path
                for machine_directory in self.machines_in(directory):
                    found.append((self.id_of(plugin_package, machine_directory.name), machine_directory))

        return found

    @staticmethod
    def machines_in(directory: Path) -> List[Path]:
        """The machines of a ``plugin/machine`` folder: its folders that hold a ``machine.py``, by name."""
        return [
            machine_directory
            for machine_directory in sorted(directory.iterdir())
            if (machine_directory / f"{FsmHandlerLocator.MACHINE_MODULE}.py").is_file()
        ]

    @classmethod
    def addon_statechart(cls, addon: Path, fsm_id: str) -> Optional[Path]:
        """
        The statechart of the machine of the addon that has the id, none when no machine of the addon has it. The machines
        of an addon are in the ``plugin/machine`` folder of its ``ontobdc`` folder, and the id of one is the name of the
        folder of the addon, ``.plugin.machine.`` and the name of its folder
        (``org.ontobdc.social.plugin.machine.whatsapp_import``). The addon is not imported: it may not be registered.

        Raises:
            LookupError: the folder of the machine holds no statechart, or more than one.
        """
        directory: Path = addon / AddonPackage.CODE_FOLDER / "plugin" / cls.RESOURCE
        if not directory.is_dir():
            return None

        machine_directory: Path
        for machine_directory in cls.machines_in(directory):
            if f"{addon.name}.plugin.{cls.RESOURCE}.{machine_directory.name}" == fsm_id:
                return cls._statechart(machine_directory)

        return None

    @staticmethod
    def _statechart(machine_directory: Path) -> Path:
        statecharts: List[Path] = sorted(machine_directory.glob("*.yaml"))
        if len(statecharts) != 1:
            raise LookupError(
                f"{machine_directory} holds {len(statecharts)} statecharts; a machine has exactly one."
            )

        return statecharts[0]

    @classmethod
    def id_of(cls, plugin_package: str, machine_name: str) -> str:
        """
        The id of the machine in the folder ``machine_name`` of the plugin package.
        """
        return f"org.{plugin_package}.{cls.RESOURCE}.{machine_name}"

    def _machines_directory(self, root_package: str, plugin_package: str) -> Optional[Path]:
        package_root: Optional[str] = (
            str(self._make_config_data_adapter().script_dir)
            if root_package == "ontobdc"
            else self._find_installed_package_root(root_package)
        )
        if package_root is None:
            return None

        relative: List[str] = plugin_package.split(".")[len(root_package.split(".")):]
        directory: Path = Path(package_root).joinpath(*relative, self.RESOURCE)
        return directory if directory.is_dir() else None
