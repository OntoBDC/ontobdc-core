import hashlib
import shutil
from pathlib import Path, PurePosixPath
from typing import ClassVar

from ontobdc.ddock.adapter.github_zip import GitHubZipAddress


class LocalPackage:
    """
    A package of ``system.obdc`` that is a folder of the machine instead of a
    GitHub repository: a relative path, which is taken from the folder that
    holds ``system.obdc`` (``addon/annotation``, ``../ddock-addon/annotation``).

    The folder is copied into the work folder of the installation, and the
    copy is what is moved from, so the folder itself is never changed. Like the
    unpacked zip of a repository, its ``src/host`` is what is merged into the
    source folder, and it is an addon when it holds a ``system.obdc`` of that scope.
    """

    CHUNK_BYTES: ClassVar[int] = 1024 * 1024

    @classmethod
    def is_path(cls, address: str) -> bool:
        """
        Whether the address is a relative path: it names no GitHub repository,
        and is not empty, absolute, or a URL of another kind.
        """
        text: str = address.strip()
        if not text or "://" in text or "\\" in text or GitHubZipAddress.repository(text) is not None:
            return False

        path: PurePosixPath = PurePosixPath(text)
        return not path.is_absolute() and not text.startswith("~") and path != PurePosixPath(".")

    @classmethod
    def folder(cls, container_path: Path, address: str) -> Path:
        """
        The folder the relative path names, taken from the container.

        Raises:
            FileNotFoundError: there is no such folder.
        """
        folder: Path = (container_path / address.strip()).resolve()
        if not folder.is_dir():
            raise FileNotFoundError(f"The package {address} is not a folder: {folder}")

        return folder

    @classmethod
    def copy(cls, container_path: Path, address: str, target: Path) -> str:
        """
        Copy the folder of the package into ``target``, which must not exist
        yet. Returns the sha256 of what was copied (the names and the bytes of
        its files, in order), the way the zip of a repository has its own.
        """
        if target.exists():
            raise FileExistsError(f"Cannot copy into a folder that exists: {target}")

        source: Path = cls.folder(container_path, address)
        if target.resolve() == source or source in target.resolve().parents:
            raise ValueError(f"The package {address} holds the work folder of the installation.")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        return cls._sha256(target)

    @classmethod
    def _sha256(cls, folder: Path) -> str:
        digest = hashlib.sha256()
        entry: Path
        for entry in sorted(path for path in folder.rglob("*") if path.is_file()):
            digest.update(entry.relative_to(folder).as_posix().encode("utf-8"))
            with entry.open("rb") as handle:
                while True:
                    chunk: bytes = handle.read(cls.CHUNK_BYTES)
                    if not chunk:
                        break
                    digest.update(chunk)

        return digest.hexdigest()
