from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

import yaml


class SystemFile:
    """
    The ``system.obdc`` of a folder: a YAML file, with another name, that says what the folder is. Its ``scope`` says it:
    a folder with a ``system.obdc`` of the scope ``addon`` is an addon, and one of the scope ``ddock`` is a system the ddock
    installs. What else the file says belongs to the one that reads it for its scope.
    """

    FILE_NAME: ClassVar[str] = "system.obdc"
    ADDON_SCOPE: ClassVar[str] = "addon"

    @classmethod
    def path_in(cls, folder: Path) -> Path:
        """Where the ``system.obdc`` of the folder is, whether it is there or not."""
        return folder / cls.FILE_NAME

    @classmethod
    def mapping(cls, folder: Path) -> Dict[str, Any]:
        """
        What the ``system.obdc`` of the folder says.

        Raises:
            FileNotFoundError: the folder has no ``system.obdc``.
            ValueError: the file is not valid YAML, or is not a mapping.
        """
        path: Path = cls.path_in(folder)
        if not path.is_file():
            raise FileNotFoundError(f"The folder {folder} has no {cls.FILE_NAME}: {path}")

        try:
            data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise ValueError(f"The {cls.FILE_NAME} of {folder} is not valid YAML: {error}") from error
        if not isinstance(data, dict):
            raise ValueError(f"The {cls.FILE_NAME} of {folder} must be a mapping.")

        return data

    @classmethod
    def addon_problem(cls, folder: Path) -> Optional[str]:
        """Why the folder is not an addon, by its ``system.obdc``; none when it says it is one."""
        try:
            data: Dict[str, Any] = cls.mapping(folder)
        except FileNotFoundError:
            return f"The folder {folder} has no {cls.FILE_NAME}: it is not an addon."
        except ValueError as error:
            return str(error)

        if data.get("scope") != cls.ADDON_SCOPE:
            return f"The {cls.FILE_NAME} of {folder} does not say it is an addon: its scope has to be '{cls.ADDON_SCOPE}'."

        return None

    @classmethod
    def is_addon(cls, folder: Path) -> bool:
        """
        Whether the folder holds a ``system.obdc`` that says the scope of an addon. A folder with no ``system.obdc``, with
        one that is not valid YAML, or with one of another scope, is not an addon.
        """
        return cls.addon_problem(folder) is None

    @classmethod
    def require_addon(cls, folder: Path) -> None:
        """
        Raises:
            ValueError: the folder is not an addon by its ``system.obdc``, and why.
        """
        problem: Optional[str] = cls.addon_problem(folder)
        if problem is not None:
            raise ValueError(problem)
