import importlib.resources as importlib_resources
from pathlib import Path
from typing import Optional, Tuple


class StatechartLocator:
    """Locate statechart YAML files without manual ``.parent`` depth-counting.

    Two resolution strategies are provided so callers never need to hardcode
    how many directories up the ``domain/machine`` folder lives:

    * **Package-based (preferred)** – uses ``importlib.resources.files`` against
      a declared Python package (for example ``"ontobdc.storage.domain.machine"``).
      This works for both source trees and installed packages (including zipped
      distributions with resource extractors).

    * **Filesystem-anchor-based (fallback)** – walks *upwards* from a caller's
      ``__file__`` looking for the first ancestor that contains a
      ``domain/machine/<filename>`` subtree. No depth-counting is required;
      the walker simply stops when the directory is found or when it reaches
      the filesystem root within a bounded number of steps.
    """

    _MACHINE_RELATIVE_PATH: Tuple[str, ...] = ("domain", "machine")
    _DEFAULT_MAX_ANCESTOR_DEPTH: int = 12

    @classmethod
    def locate_via_package(
        cls,
        statechart_package: str,
        statechart_filename: str,
    ) -> Path:
        """Resolve a statechart via its owning Python package name.

        Parameters
        ----------
        statechart_package:
            Fully-qualified package whose ``domain/machine`` subpackage contains
            the YAML file. Example: ``"ontobdc.storage.domain.machine"``.
        statechart_filename:
            Basename of the statechart file, for example
            ``"standard_container_attach.yaml"``.

        Returns
        -------
        Path
            Resolved absolute path to the statechart file.  Raises if the file
            does not exist (callers rely on an explicit error instead of a
            silent wrong path).
        """
        directory: Any = importlib_resources.files(statechart_package)
        try:
            file_ref: Any = directory / statechart_filename
        except TypeError:
            package_directory: Path = Path(str(directory))
            file_ref = package_directory / statechart_filename
        resolved: Path = Path(str(file_ref)).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Statechart not found via package '{statechart_package}': "
                f"{resolved}"
            )
        return resolved

    @classmethod
    def locate_via_anchor(
        cls,
        anchor_file: str,
        statechart_filename: str,
        *,
        max_depth: Optional[int] = None,
    ) -> Path:
        """Walk *upwards* from ``anchor_file`` (typically ``__file__``) looking
        for ``domain/machine/<statechart_filename>``.

        The algorithm does not rely on a known number of ``.parent`` hops; it
        simply probes each ancestor until one contains the canonical
        ``domain/machine`` layout.  This means the same helper works from any
        nesting depth inside a module (e.g. ``adapter/machine.py`` vs
        ``adapter/attachment/machine.py`` vs
        ``plugin/component/feature/machine.py``).

        Parameters
        ----------
        anchor_file:
            Typically the caller's own ``__file__`` value.  Any path whose
            ancestors eventually reach ``domain/machine`` works.
        statechart_filename:
            Basename of the statechart YAML file.
        max_depth:
            Safety bound for the ancestor walk.  Defaults to a generous
            ``12``; bump only for exceptionally deep package hierarchies.

        Returns
        -------
        Path
            Resolved absolute path to the matching statechart.  Raises
            ``FileNotFoundError`` if the directory does not exist within the
            allowed walk depth.
        """
        limit: int = max_depth if max_depth is not None else cls._DEFAULT_MAX_ANCESTOR_DEPTH
        current: Path = Path(anchor_file).resolve().parent
        machine_parts: Path = Path(*cls._MACHINE_RELATIVE_PATH)
        for _ in range(limit):
            candidate: Path = (current / machine_parts / statechart_filename).resolve()
            if candidate.is_file():
                return candidate
            next_parent: Path = current.parent
            if next_parent == current:
                break
            current = next_parent
        raise FileNotFoundError(
            f"Statechart '{statechart_filename}' not found walking "
            f"ancestors of '{anchor_file}' (depth={limit})."
        )

    @classmethod
    def locate(
        cls,
        anchor_file: str,
        statechart_filename: str,
        *,
        statechart_package: Optional[str] = None,
        max_ancestor_depth: Optional[int] = None,
    ) -> Path:
        """Unified public entry-point – try package resolution first, then
        fall back to the ancestor-walk.

        Parameters
        ----------
        anchor_file:
            Caller ``__file__`` anchor used by the filesystem fallback.
        statechart_filename:
            Statechart basename (for example ``"standard_container_attach.yaml"``).
        statechart_package:
            Optional package hint for the preferred ``importlib.resources``
            path.  When omitted the filesystem walker is used directly.
        max_ancestor_depth:
            Optional safety bound forwarded to :meth:`locate_via_anchor`.

        Returns
        -------
        Path
            Resolved absolute path to the statechart file.
        """
        if statechart_package:
            try:
                return cls.locate_via_package(
                    statechart_package,
                    statechart_filename,
                )
            except (ModuleNotFoundError, FileNotFoundError):
                pass
        return cls.locate_via_anchor(
            anchor_file,
            statechart_filename,
            max_depth=max_ancestor_depth,
        )
