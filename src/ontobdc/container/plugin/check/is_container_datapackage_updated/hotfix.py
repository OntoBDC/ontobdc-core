from pathlib import Path

from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer


def main(
    print_log: callable = None,
    container_path: str = None,
    root_path: str = None,
) -> int:
    del root_path
    if not container_path:
        return 1

    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    try:
        ContainerDataPackageSynchronizer().sync(resolved_container_path)
    except (OSError, ValueError) as error:
        if print_log is not None:
            print_log(
                "ERROR",
                "Hotfix Container Data Package Updated",
                f"Failed to synchronize the container Data Package descriptor: {error}",
            )
        return 1

    return 0
