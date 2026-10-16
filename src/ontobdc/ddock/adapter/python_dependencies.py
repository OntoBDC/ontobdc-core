import subprocess
import sys
from importlib import metadata
from typing import ClassVar, Dict, List

from ontobdc.ddock.domain.model.system_descriptor import PythonDependency


class PythonDependencies:
    """
    Install the Python dependencies of a system with the ``pip`` of the Python
    that runs OntoBDC, and say what version of each ended up installed.
    """

    TAIL_LINES: ClassVar[int] = 12

    @classmethod
    def satisfied(cls, dependencies: List[PythonDependency]) -> bool:
        """
        Whether every dependency is installed, at its version when it has one.
        """
        dependency: PythonDependency
        for dependency in dependencies:
            try:
                version: str = metadata.version(dependency.name)
            except metadata.PackageNotFoundError:
                return False

            if dependency.version and version != dependency.version:
                return False

        return True

    @classmethod
    def install(cls, dependencies: List[PythonDependency]) -> Dict[str, str]:
        """
        Install the dependencies, each at its version when it has one. Returns
        the version installed of each, by name.

        Raises:
            RuntimeError: ``pip`` failed, or a dependency with a version is
                installed at another one.
        """
        if not dependencies:
            return {}

        completed: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-m", "pip", "install", *[dependency.requirement() for dependency in dependencies]],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            tail: str = "\n".join((completed.stderr or completed.stdout).strip().splitlines()[-cls.TAIL_LINES:])
            raise RuntimeError(f"pip could not install the Python dependencies:\n{tail}")

        installed: Dict[str, str] = {}
        dependency: PythonDependency
        for dependency in dependencies:
            version: str = metadata.version(dependency.name)
            if dependency.version and version != dependency.version:
                raise RuntimeError(
                    f"{dependency.name} is installed at {version}, not at {dependency.version} as system.obdc asks."
                )
            installed[dependency.name] = version

        return installed
