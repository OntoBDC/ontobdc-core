import subprocess
from pathlib import Path
from typing import ClassVar, List


class NodeBuild:
    """
    Compile the node application in a folder of a project: install its dependencies with
    ``npm install``, then build it with ``npm run build``.
    """

    COMMANDS: ClassVar[List[List[str]]] = [["npm", "install"], ["npm", "run", "build"]]
    COMMAND_TEXT: ClassVar[str] = "npm install && npm run build"
    TAIL_LINES: ClassVar[int] = 12

    @classmethod
    def run(cls, folder: Path) -> None:
        """
        Install the dependencies and run the build in the folder.

        Raises:
            RuntimeError: ``npm`` is not installed, or one of the commands failed.
        """
        command: List[str]
        for command in cls.COMMANDS:
            try:
                completed: subprocess.CompletedProcess[str] = subprocess.run(
                    command,
                    cwd=folder,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as error:
                raise RuntimeError("npm is not installed, so the node application cannot be compiled.") from error

            if completed.returncode != 0:
                tail: str = "\n".join((completed.stderr or completed.stdout).strip().splitlines()[-cls.TAIL_LINES:])
                raise RuntimeError(f"{' '.join(command)} failed:\n{tail}")
