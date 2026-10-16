import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import ClassVar, List


class ZipArchive:
    """
    Download the zip of a repository and unpack it.

    A zip of GitHub holds one folder with everything inside; unpacking puts
    what is inside that folder in the target, not the folder that holds it.
    """

    TIMEOUT_SECONDS: ClassVar[int] = 60
    CHUNK_BYTES: ClassVar[int] = 1024 * 1024

    @classmethod
    def fetch(cls, address: str, target: Path) -> str:
        """
        Download the zip at ``address`` and unpack it into ``target``, which
        must not exist yet. Returns the sha256 of the zip.

        Raises:
            OSError: the zip could not be downloaded.
            ValueError: what came is not a zip, or it has a member that would
                be written outside ``target``.
            FileExistsError: ``target`` exists.
        """
        if target.exists():
            raise FileExistsError(f"Cannot unpack into a folder that exists: {target}")

        with tempfile.TemporaryDirectory(prefix="ddock-zip-") as scratch:
            archive_path: Path = Path(scratch) / "archive.zip"
            digest = hashlib.sha256()
            with urllib.request.urlopen(address, timeout=cls.TIMEOUT_SECONDS) as response, archive_path.open("wb") as handle:
                while True:
                    chunk: bytes = response.read(cls.CHUNK_BYTES)
                    if not chunk:
                        break
                    digest.update(chunk)
                    handle.write(chunk)

            cls.unpack(archive_path, target)

        return digest.hexdigest()

    @classmethod
    def unpack(cls, archive_path: Path, target: Path) -> None:
        """
        Unpack the zip into ``target``, without the one folder that holds
        everything when the zip has one.
        """
        if not zipfile.is_zipfile(archive_path):
            raise ValueError(f"What was downloaded is not a zip: {archive_path.name}")

        with tempfile.TemporaryDirectory(prefix="ddock-unpack-") as scratch:
            staging: Path = Path(scratch).resolve()
            with zipfile.ZipFile(archive_path) as archive:
                member: str
                for member in archive.namelist():
                    if staging not in (staging / member).resolve().parents:
                        raise ValueError(f"The zip has a member outside its folder: {member}")
                archive.extractall(staging)

            entries: List[Path] = list(staging.iterdir())
            inside: Path = entries[0] if len(entries) == 1 and entries[0].is_dir() else staging
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(inside), str(target))
