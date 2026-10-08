import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, ClassVar, List, Optional, Tuple, Type


class FsmHandlerLocator:
    """
    Find the handler that runs the statechart in a YAML file.

    The handler is found by the layout of the folder, not by anything the
    YAML says: a machine is a package whose statechart sits beside a
    ``machine.py``, and that module defines the one
    ``*StateTransitionHandler`` class that drives it. The YAML is given as a
    path, or as a path inside an installed top-level package
    (``ontobdc/annotation/.../standard_x.yaml``), which is how a caller that
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
        ``sys.path`` entry that holds it.
        """
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
