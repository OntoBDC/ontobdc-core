import shutil
import time
from pathlib import Path
from typing import Optional


def remove_directory_tree(
    path: Path,
    *,
    attempts: int = 5,
    initial_delay_seconds: float = 0.2,
) -> None:
    """Remove `path` and everything under it, retrying transient Windows locks.

    Cloud-sync clients (OneDrive, Dropbox, etc.) can briefly hold an open
    handle on a file while indexing or uploading it, which surfaces as
    `PermissionError` (`WinError 5`) or `OSError` (`WinError 32`) from
    `shutil.rmtree` even though nothing in this process is using the file.
    The lock is normally released within a second, so a short retry with
    backoff resolves it without the caller needing to know Windows/OneDrive
    specifics. Raises the last error if `path` is still locked after all
    attempts.
    """
    last_error: Optional[OSError] = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except OSError as error:
            last_error = error
            if attempt < attempts - 1:
                time.sleep(initial_delay_seconds * (attempt + 1))

    raise OSError(
        f"Could not remove {path}: still in use after {attempts} attempts. "
        "This is commonly a cloud-sync client (OneDrive, Dropbox, etc.) "
        "briefly holding a file handle open -- wait a moment and retry."
    ) from last_error
