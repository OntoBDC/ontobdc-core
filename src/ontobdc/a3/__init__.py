
from ontobdc.cli.init import is_extra_enabled
from ontobdc.storage.domain.port.repository import DatasetRepositoryPort


def is_enabled() -> bool:
    """
    Checks if all dependencies defined in the 'a3' extra
    of pyproject.toml are installed.
    """
    return is_extra_enabled("a3")


def get_lifecycle_dir(dataset: DatasetRepositoryPort | None = None) -> str:
    if dataset is None:
        raise ValueError("A3 lifecycle directory depends on a registered dataset.")

    return str(dataset.path)
