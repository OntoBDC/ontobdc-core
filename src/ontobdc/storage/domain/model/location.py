import os
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from ontobdc.storage.domain.exception.location import InconsistentStorageIndexError


class StorageLocation:
    """
    How the locations recorded in a storage index are read.

    A storage root is wherever its ``.__ontobdc__`` marker is found, not the
    absolute path its graphs recorded when they were written: the same root
    may be moved on disk, or be created in one file system (e.g. a browser's
    virtual one) and opened in another. Every location recorded under the
    root's own recorded location is therefore read relative to the root's
    current place. A location outside it makes the index inconsistent, since
    every container lives under its root.
    """

    @staticmethod
    def to_path(location: str) -> Path:
        """
        The filesystem path of a recorded location: a ``file://`` URI or a
        plain path.
        """
        parsed = urlparse(location)
        if parsed.scheme and parsed.scheme != "file":
            raise ValueError(
                f"Unsupported container location scheme: {parsed.scheme}"
            )

        raw_path: str = unquote(parsed.path if parsed.scheme else location)
        if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2:
            if raw_path[2] == ":":
                raw_path = raw_path[1:]

        return Path(raw_path).expanduser().resolve()

    @staticmethod
    def rebase(
        path: Path,
        recorded_root: Optional[Path],
        current_root: Path,
    ) -> Path:
        """
        Where a recorded path is now: the same place relative to the root's
        current location. An index whose root recorded no location of its own
        (one written before ``init`` ran) has nothing to rebase from, so its
        paths are taken as recorded.

        Raises:
            InconsistentStorageIndexError: the path is outside the root's
                recorded location.
        """
        if recorded_root is None:
            return path

        try:
            relative: Path = path.relative_to(recorded_root)
        except ValueError:
            raise InconsistentStorageIndexError(path, recorded_root) from None

        return current_root / relative
