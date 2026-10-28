import re
import urllib.error
import urllib.request
from typing import Callable, ClassVar, Optional, Pattern, Tuple


class GitHubZipAddress:
    """
    The address of the zip of a branch of a GitHub repository.

    A person names a repository the way they have it at hand: its page, its
    clone address, a link into a branch or a file of it, the address of a zip
    of it, or ``github:<owner>/<repo>``. Whatever the form, the zip is the one
    of the ``master`` branch (``https://github.com/<owner>/<repo>/archive/refs/heads/master.zip``)
    when the repository has one, else the one of the ``main`` branch. An address
    that does not name a GitHub repository, or a repository that has neither
    branch (or that cannot be reached), has no zip.
    """

    # The branches whose zip is looked for, in this order.
    BRANCHES: ClassVar[Tuple[str, ...]] = ("master", "main")
    TIMEOUT_SECONDS: ClassVar[int] = 10
    # The repository of the official OntoBDC dDock: what a system that names
    # no remote of its own installs from.
    DEFAULT_REPOSITORY: ClassVar[str] = "https://github.com/OntoBDC/ontobdc-ddock"

    OWNER: ClassVar[str] = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    REPOSITORY: ClassVar[str] = r"[A-Za-z0-9._-]+"
    # github.com/<owner>/<repo>[...], with an optional scheme and ``www.``.
    PAGE: ClassVar[Pattern[str]] = re.compile(
        rf"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>{OWNER})/(?P<repo>{REPOSITORY})(?:[/?#].*)?$"
    )
    # codeload.github.com/<owner>/<repo>/zip/...
    CODELOAD: ClassVar[Pattern[str]] = re.compile(
        rf"^(?:https?://)?codeload\.github\.com/(?P<owner>{OWNER})/(?P<repo>{REPOSITORY})(?:[/?#].*)?$"
    )
    # git@github.com:<owner>/<repo>.git and ssh://git@github.com/<owner>/<repo>.git
    SSH: ClassVar[Pattern[str]] = re.compile(
        rf"^(?:ssh://)?git@github\.com[:/](?P<owner>{OWNER})/(?P<repo>{REPOSITORY})(?:[/?#].*)?$"
    )
    # github:<owner>/<repo>
    SHORT: ClassVar[Pattern[str]] = re.compile(
        rf"^github:(?P<owner>{OWNER})/(?P<repo>{REPOSITORY})(?:[/?#].*)?$"
    )

    @classmethod
    def repository(cls, address: str) -> Optional[Tuple[str, str]]:
        """
        The owner and the name of the repository the address names, or None
        when it names no GitHub repository.
        """
        text: str = address.strip()
        pattern: Pattern[str]
        for pattern in (cls.PAGE, cls.CODELOAD, cls.SSH, cls.SHORT):
            match: Optional["re.Match[str]"] = pattern.match(text)
            if match is None:
                continue

            name: str = match.group("repo")
            if name.endswith(".git"):
                name = name[: -len(".git")]
            if not name or name in (".", ".."):
                return None

            return match.group("owner"), name

        return None

    @classmethod
    def page_of(cls, owner: str, name: str) -> str:
        """
        The address of the page of the repository.
        """
        return f"https://github.com/{owner}/{name}"

    @classmethod
    def zip_of(cls, owner: str, name: str, branch: str) -> str:
        """
        The address of the zip of the branch of the repository.
        """
        return f"{cls.page_of(owner, name)}/archive/refs/heads/{branch}.zip"

    @classmethod
    def repository_address(cls, address: str) -> Optional[str]:
        """
        The address of the page of the repository the address names, whatever
        the form it names it in, or None when it names no GitHub repository.
        """
        repository: Optional[Tuple[str, str]] = cls.repository(address)
        if repository is None:
            return None

        return cls.page_of(*repository)

    @classmethod
    def resolve(
        cls,
        address: str,
        exists: Optional[Callable[[str], bool]] = None,
    ) -> Optional[str]:
        """
        The address of the zip of the first of ``BRANCHES`` the repository the
        address names has, or None when the address names no GitHub repository
        or the repository has none of them. ``exists`` says whether a zip is
        there; by default it asks GitHub.
        """
        repository: Optional[Tuple[str, str]] = cls.repository(address)
        if repository is None:
            return None

        is_there: Callable[[str], bool] = exists if exists is not None else cls.is_published
        branch: str
        for branch in cls.BRANCHES:
            candidate: str = cls.zip_of(*repository, branch)
            if is_there(candidate):
                return candidate

        return None

    @classmethod
    def is_published(cls, zip_address: str) -> bool:
        """
        Whether GitHub serves the zip: it answers success to a request for its
        head, redirects included. A branch that does not exist answers 404, and
        so does a private repository; any other failure (no network, a limit
        of GitHub) is taken as not served, because nothing is known about it.
        """
        request: urllib.request.Request = urllib.request.Request(zip_address, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=cls.TIMEOUT_SECONDS) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False
