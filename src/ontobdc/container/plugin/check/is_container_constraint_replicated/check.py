from typing import Callable, Optional

from ontobdc.container.adapter.constraint_replication import ConstraintReplication


def main(
    print_log: Optional[Callable[..., None]] = None,
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
    config: Optional[str] = None,
) -> int:
    """
    Zero when the container holds the constraints the config body declares, or when there is no body to
    compare with; one when it does not; two when the body cannot be read.
    """
    del container_path
    if not root_path:
        return 2

    try:
        replicated: bool = ConstraintReplication.is_replicated(root_path, config)
    except ValueError as error:
        if print_log is not None:
            print_log("ERROR", "Check Container Constraints Replicated", str(error))

        return 2

    if not replicated and print_log is not None:
        print_log(
            "WARNING",
            "Check Container Constraints Replicated",
            "The constraints of the application are not the ones the container holds: refresh it to replicate them.",
        )

    return 0 if replicated else 1
