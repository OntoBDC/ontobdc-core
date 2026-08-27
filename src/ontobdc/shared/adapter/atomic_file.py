"""Atomic file writer (write-then-swap via tempfile + ``os.replace``).

Any capability that mutates a binary or structured file (IFC models,
pickled graphs, XLSX workbooks, ZIP datasets, …) must use atomic writes
to avoid leaving a half-written / corrupted file behind if the writer
or the Python process crashes mid-stream.

Usage pattern:

    AtomicFileWriter.write(model_path, lambda tmp: model.write(str(tmp)))

The ``writer_callable`` receives a ``Path`` pointing to the temp file
and should write its output there; the adapter takes care of creating
the temp file in the same directory as the target, calling the writer,
swapping atomically, and cleaning up on any exception (including a
``raise`` from inside the writer itself).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable


class AtomicFileWriter:
    """Write a file atomically: tempfile in target directory, then ``os.replace``."""

    @staticmethod
    def write(destination: Path, writer_callable: Callable[[Path], None]) -> None:
        """Invoke ``writer_callable(temp_path)`` and swap the result onto ``destination``.

        ``temp_path`` lives in the same parent directory as ``destination``
        so ``os.replace`` stays inside a single filesystem (no cross-device
        rename errors). Cleanup of the temp file is guaranteed via a
        ``finally`` block.
        """
        target = Path(destination).expanduser().resolve()
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=str(target.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            writer_callable(temp_path)
            os.replace(temp_path, target)
        finally:
            if temp_path.exists():
                temp_path.unlink()
