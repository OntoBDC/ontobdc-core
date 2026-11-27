import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import ClassVar, List, Tuple
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from ontobdc.shared.adapter.system_file import SystemFile


class AddonLocator:
    """
    Locates the folder of an addon, from the folder or the address it is given as, and judges that it is one: a folder that
    has a ``system.obdc`` that says its scope is ``addon`` (see :class:`SystemFile`). It is what ``ontobdc init --addon``
    installs in the storage. An addon that has no machines (one that only adds to the ddock) is an addon all the same.
    An addon on the internet is given by the address of its folder in a repository of GitHub, which is downloaded as a ZIP
    at the ref the address names, each time, so what is used is what the address says now; only the domains of
    ``ALLOWED_DOMAINS`` are reached.
    """

    ALLOWED_DOMAINS: ClassVar[Tuple[str, ...]] = ("github.com",)
    ARCHIVE_ADDRESS: ClassVar[str] = "https://github.com/{owner}/{repo}/archive/{ref}.zip"
    TIMEOUT_SECONDS: ClassVar[int] = 120
    CACHE_FOLDER: ClassVar[str] = "ontobdc-addon"

    @classmethod
    def locate(cls, source: str) -> Path:
        """
        The folder of the addon a source names: a folder on this machine, or the address of a folder of a repository
        of GitHub (``https://github.com/<owner>/<repo>/tree/<ref>/<folder>``), which is brought to this machine.

        Raises:
            FileNotFoundError: the folder does not exist.
            ValueError: the address is not of an allowed domain or does not name a folder of a repository at a ref, the
                repository cannot be downloaded, or the folder is not an addon.
        """
        scheme: str = urlparse(source).scheme
        if not scheme:
            return cls.validated(Path(source))
        if scheme not in ("http", "https"):
            raise ValueError(f"{source} is not an http or https address or local filesystem path.")

        owner, repo, ref, parts = cls._parse(source)
        return cls.validated(cls.fetch(owner, repo, ref).joinpath(*parts))

    @classmethod
    def validated(cls, addon: Path) -> Path:
        """
        The resolved folder of the addon: a folder that has a ``system.obdc`` that says its scope is ``addon``.

        Raises:
            FileNotFoundError: the folder does not exist.
            ValueError: the folder is not an addon by its ``system.obdc`` (see :class:`SystemFile`).
        """
        folder: Path = addon.expanduser().resolve()
        if not folder.is_dir():
            raise FileNotFoundError(f"The addon {addon} is not a folder.")

        SystemFile.require_addon(folder)

        return folder

    @classmethod
    def fetch(cls, owner: str, repo: str, ref: str) -> Path:
        """The repository at the ref, downloaded and unpacked in a folder of the temporary files."""
        target: Path = Path(tempfile.gettempdir()) / cls.CACHE_FOLDER / owner / repo / ref.replace("/", "-")
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        archive: Path = target / "repository.zip"
        address: str = cls.ARCHIVE_ADDRESS.format(owner=owner, repo=repo, ref=ref)
        try:
            with urlopen(address, timeout=cls.TIMEOUT_SECONDS) as response, archive.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except (URLError, OSError) as error:
            raise ValueError(f"The repository {owner}/{repo} at {ref} cannot be downloaded from {address}: {error}") from error

        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(target / "unpacked")
        archive.unlink()
        roots: List[Path] = [entry for entry in (target / "unpacked").iterdir() if entry.is_dir()]
        if len(roots) != 1:
            raise ValueError(f"The ZIP of {owner}/{repo} at {ref} holds {len(roots)} folders at its top; it has to hold one.")

        return roots[0]

    @classmethod
    def _parse(cls, address: str) -> Tuple[str, str, str, List[str]]:
        """The owner, the repository, the ref and the segments of the path of the folder, of an address of GitHub."""
        parsed = urlparse(address)
        host: str = (parsed.hostname or "").lower()
        if host not in cls.ALLOWED_DOMAINS:
            raise ValueError(f"The domain {host or address} is not allowed; the allowed ones are {', '.join(cls.ALLOWED_DOMAINS)}.")

        # github.com/<owner>/<repo>/tree/<ref>/<folder...>
        segments: List[str] = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 5 or segments[2] != "tree":
            raise ValueError(f"{address} does not name a folder of a repository at a ref (…/tree/<ref>/<folder>).")

        return segments[0], segments[1], segments[3], segments[4:]
