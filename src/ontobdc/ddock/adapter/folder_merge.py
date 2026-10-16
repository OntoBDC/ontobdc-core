import shutil
from pathlib import Path
from typing import List, Optional


class FolderMerge:
    """
    Put the contents of a folder into another, merging the folders both have.

    A file is moved when it is still in the source. A file that the target
    already has was moved before, so it is never overwritten, and its copy
    in the source is dropped: what is left in the source is what was not
    moved yet.
    """

    @classmethod
    def files(cls, folder: Path) -> List[str]:
        """
        The files in the folder, by their path from it.
        """
        if not folder.is_dir():
            return []

        return sorted(entry.relative_to(folder).as_posix() for entry in folder.rglob("*") if entry.is_file())

    @staticmethod
    def covers(entries: List[str], name: str) -> bool:
        """
        Whether the file is one of the entries, or in one that is a folder.
        """
        return any(name == entry or name.startswith(f"{entry}/") for entry in entries)

    @classmethod
    def merge(cls, source: Path, target: Path, only: Optional[List[str]] = None) -> List[Path]:
        """
        Move the contents of ``source`` into ``target``, or only the ``only``
        entries of it when they are given. Returns the files put there.
        """
        moved: List[Path] = []
        entry: Path
        for entry in sorted(source.rglob("*")):
            destination: Path = target / entry.relative_to(source)
            if entry.is_dir():
                if only is None:
                    destination.mkdir(parents=True, exist_ok=True)
                continue

            if only is not None and not cls.covers(only, entry.relative_to(source).as_posix()):
                continue

            if destination.exists():
                entry.unlink()
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(destination))
            moved.append(destination)

        return moved
