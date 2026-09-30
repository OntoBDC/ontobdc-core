from pathlib import Path
import importlib.resources as importlib_resources
from importlib.resources.abc import Traversable


class StatechartLocator:
    """
    Resolve a statechart YAML file through the package that owns it.

    A statechart is shipped as package data inside the ``plugin/machine/<name>``
    package of the domain it describes, so resolution goes through
    ``importlib.resources`` against that package name. The result is the same
    in a source tree and in an installed distribution, and it never depends on
    where the calling module happens to sit in the directory tree.

    There is a single resolution strategy on purpose. A package that ships
    without its statechart raises here, at the first call, instead of falling
    back to a filesystem search that would keep working by accident for as
    long as a source tree is around.

    Statecharts are handed to ``sismic`` as real files, so a zipped
    distribution is rejected explicitly rather than silently mishandled.
    Supporting one is a contained change: expose
    ``importlib.resources.as_file`` as a context manager and use the
    statechart inside the ``with`` block.
    """

    @classmethod
    def locate(
        cls,
        statechart_package: str,
        statechart_filename: str,
    ) -> Path:
        """
        Return the path of ``statechart_filename`` inside ``statechart_package``.

        :param statechart_package: Package holding the statechart as package
            data, for example
            ``"ontobdc.container.plugin.machine.container_create"``.
        :param statechart_filename: Statechart basename, for example
            ``"standard_container_create.yaml"``.
        :raises ModuleNotFoundError: The package does not exist.
        :raises TypeError: The package is not backed by the filesystem.
        :raises FileNotFoundError: The package ships without the statechart.
        """
        statechart_resource: Traversable = (
            importlib_resources.files(statechart_package) / statechart_filename
        )

        if not isinstance(statechart_resource, Path):
            raise TypeError(
                f"Statechart '{statechart_filename}' in package "
                f"'{statechart_package}' is not backed by the filesystem; "
                f"zipped distributions are not supported."
            )

        if not statechart_resource.is_file():
            raise FileNotFoundError(
                f"Package '{statechart_package}' ships without the statechart "
                f"'{statechart_filename}': {statechart_resource}"
            )

        return statechart_resource
