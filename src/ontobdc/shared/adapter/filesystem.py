import os
import shutil
import stat
import time
from pathlib import Path
from typing import Optional


def _clear_readonly_and_retry(function, path, exc_info) -> None:
    """`shutil.rmtree(onexc=...)` handler: drop the read-only bit and retry.

    Cloud-sync clients (OneDrive, Dropbox, etc.) commonly leave synced files
    marked read-only, which raises `PermissionError` on delete regardless of
    how many times the operation is retried -- clearing the bit is required,
    not optional. If the retry still fails (a genuine open-handle lock
    rather than a permission bit), the exception propagates so the caller's
    own attempt/backoff loop can retry the whole operation instead.
    """
    del exc_info
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_directory_tree(
    path: Path,
    *,
    attempts: int = 5,
    initial_delay_seconds: float = 0.3,
) -> None:
    """Remove `path` and everything under it, tolerating Windows/cloud-sync locks.

    Two distinct failure modes show up as the same `PermissionError`
    (`WinError 5`) / `OSError` (`WinError 32`) on Windows under a cloud-sync
    folder (OneDrive, Dropbox, etc.):

    - A file is marked read-only (cloud-sync clients do this routinely) --
      permanent until the attribute is cleared; retrying alone never helps.
    - The sync client briefly holds an open handle while indexing/uploading
      -- transient, normally clears within a second or two.

    Handles the first via `onexc`, and the second via a short retry loop
    around the whole `shutil.rmtree` call. Raises the last error if `path`
    is still unremovable after all attempts.
    """
    last_error: Optional[OSError] = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path, onexc=_clear_readonly_and_retry)
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


def remove_file(
    path: Path,
    *,
    attempts: int = 5,
    initial_delay_seconds: float = 0.3,
) -> None:
    """Remove a single file, tolerating the same Windows/cloud-sync locks
    `remove_directory_tree` handles -- see its docstring for the two
    distinct failure modes this covers.
    """
    last_error: Optional[OSError] = None
    for attempt in range(attempts):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError as error:
            last_error = error
            try:
                os.chmod(path, stat.S_IWRITE)
                path.unlink()
                return
            except FileNotFoundError:
                return
            except OSError as retry_error:
                last_error = retry_error
        except OSError as error:
            last_error = error

        if attempt < attempts - 1:
            time.sleep(initial_delay_seconds * (attempt + 1))

    raise OSError(
        f"Could not remove {path}: still in use after {attempts} attempts. "
        "This is commonly a cloud-sync client (OneDrive, Dropbox, etc.) "
        "briefly holding a file handle open -- wait a moment and retry."
    ) from last_error
