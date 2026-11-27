import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import ClassVar, Dict, List, Optional


class AddonPackage:
    """
    The Python code of an addon, made importable as a module of OntoBDC without installing anything.

    An addon is a folder (``org.ontobdc.social``) whose ``ontobdc`` folder holds the code, laid out as a module of
    OntoBDC: ``plugin/machine/<name>`` and ``plugin/capability/transformation``. The folder is registered as the
    module ``ontobdc.<component>`` (the last name of the addon: ``ontobdc.social``), and what is in it is imported
    by that name. Nothing registers an addon by itself: whoever runs the code of one asks for it, here or through
    the environment variable that the process of a job is started with.
    """

    ENVIRONMENT_KEY: ClassVar[str] = "ONTOBDC_ADDON_PATH"
    CODE_FOLDER: ClassVar[str] = "ontobdc"
    PARENT_MODULE: ClassVar[str] = "ontobdc"
    _registered: ClassVar[Dict[str, Path]] = {}

    @classmethod
    def module_name(cls, addon: Path) -> str:
        """``ontobdc.social`` for the addon ``org.ontobdc.social``."""
        return f"{cls.PARENT_MODULE}.{addon.name.rsplit('.', 1)[-1]}"

    @classmethod
    def register(cls, addon: Path) -> str:
        """
        Makes the ``ontobdc`` folder of the addon the module of its component, and gives the module name.

        Raises:
            FileNotFoundError: the addon has no ``ontobdc`` folder with an ``__init__.py``.
            ValueError: another folder is already registered under the name of the module.
        """
        folder: Path = addon.expanduser().resolve() / cls.CODE_FOLDER
        init: Path = folder / "__init__.py"
        if not init.is_file():
            raise FileNotFoundError(f"The addon {addon} has no {cls.CODE_FOLDER}/__init__.py.")

        name: str = cls.module_name(addon.expanduser().resolve())
        known: Optional[Path] = cls._registered.get(name)
        if known is not None:
            if known != folder:
                raise ValueError(f"The module {name} is already the folder {known}, not {folder}.")
            return name

        spec = importlib.util.spec_from_file_location(name, init, submodule_search_locations=[str(folder)])
        if spec is None or spec.loader is None:
            raise ImportError(f"The folder {folder} cannot be imported as {name}.")

        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(importlib.import_module(cls.PARENT_MODULE), name.rsplit(".", 1)[-1], module)
        cls._registered[name] = folder
        return name

    @classmethod
    def from_environment(cls) -> List[str]:
        """Registers the addons the environment names (folders separated by the path separator of the system)."""
        value: str = os.environ.get(cls.ENVIRONMENT_KEY, "")
        return [cls.register(Path(entry)) for entry in value.split(os.pathsep) if entry.strip()]

    @classmethod
    def registered(cls) -> Dict[str, Path]:
        """The ``ontobdc`` folder of each addon registered, by the name of its module."""
        return dict(cls._registered)

    @classmethod
    def package_of(cls, directory: Path) -> Optional[str]:
        """The dotted name of the package a folder is, when it is inside an addon registered; none otherwise."""
        resolved: Path = directory.resolve()
        name: str
        folder: Path
        for name, folder in cls._registered.items():
            if folder in (resolved, *resolved.parents):
                return ".".join((name, *resolved.relative_to(folder).parts))

        return None
