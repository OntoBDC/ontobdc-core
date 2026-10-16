
from pathlib import Path
from typing import ClassVar, Optional, Tuple
from urllib.parse import unquote, urlparse


class RemoteContainerUrl:
    """
    The address of a remote OntoBDC Container: an ``http`` or ``https`` URL
    that points to the project's ``.obdc`` file.
    """

    SCHEMES: ClassVar[Tuple[str, ...]] = ("http", "https")
    DEFAULT_FILE_NAME: ClassVar[str] = "remote.obdc"

    @staticmethod
    def is_valid(url: str) -> bool:
        """
        Whether the URL is an ``http`` or ``https`` address with a host.
        """
        if not isinstance(url, str) or not url.strip():
            return False

        try:
            parsed = urlparse(url.strip())
            hostname = parsed.hostname
        except ValueError:
            return False

        return parsed.scheme in RemoteContainerUrl.SCHEMES and bool(hostname)

    @staticmethod
    def file_name(url: str) -> str:
        """
        The name to save the remote file under: the last segment of the URL
        path, never a path of its own. A URL without one falls back to a
        default name.
        """
        path: str = unquote(urlparse(url.strip()).path)
        name: str = path.rsplit("/", 1)[-1].replace("\\", "/").rsplit("/", 1)[-1]
        if name in ("", ".", ".."):
            return RemoteContainerUrl.DEFAULT_FILE_NAME

        return name

    @staticmethod
    def destination(url: str, directory: Optional[str] = None) -> Path:
        """
        Where the remote file is saved: under its own name, in ``directory``
        or, when none is given, in the current directory.
        """
        base: Path = (
            Path(directory) if isinstance(directory, str) and directory.strip()
            else Path.cwd()
        )

        return base.expanduser().resolve() / RemoteContainerUrl.file_name(url)
