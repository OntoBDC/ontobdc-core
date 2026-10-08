from pathlib import Path
from typing import Callable

CheckMain = Callable[..., int]


class CheckedRepair:
    """
    Bring one piece of the project to what its check observes.

    The hotfix runs only when the check does not hold, and the check is asked
    again afterwards: a repair that leaves nothing the check can observe is a
    failure, not a success.
    """

    @staticmethod
    def ensure(
        check: CheckMain,
        hotfix: CheckMain,
        root_path: Path,
        subject: str,
    ) -> None:
        if check(root_path=str(root_path)) == 0:
            return

        if hotfix(root_path=str(root_path)) != 0:
            raise ValueError(f"Failed to repair {subject} during CLI init.")

        if check(root_path=str(root_path)) != 0:
            raise ValueError(f"{subject} is still invalid after the CLI init repair.")
