from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class ArchiveFiles(BaseModel):
    """
    A zip that was unpacked: where it came from, its sha256, and the files of
    it that go into the project, by their path from the source folder.
    """

    zip: str
    sha256: str
    files: List[str] = Field(default_factory=list)

    def present_in(self, destination: Path) -> bool:
        """
        Whether every one of the files is in the destination.
        """
        return all((destination / name).is_file() for name in self.files)


class UnpackedPackage(BaseModel):
    """
    A package of system.obdc, unpacked in the work folder of the installation.
    """

    address: str
    path: Path
    archive: ArchiveFiles


class LockedDdock(ArchiveFiles):
    """
    What the lock says about ddock: its zip and the source folder it was installed into.
    """

    source: str


class LockedPackage(ArchiveFiles):
    """
    What the lock says about a package that was installed.
    """

    address: str


class LockedPythonDependency(BaseModel):
    """
    A Python dependency as the lock has it: the version asked for, if any, and
    the version that ended up installed.
    """

    name: str
    requested: Optional[str] = None
    installed: str


class SystemLockContent(BaseModel):
    """
    The content of ``system.obdc.lock``.
    """

    descriptor_sha256: str
    python: List[LockedPythonDependency] = Field(default_factory=list)
    ddock: LockedDdock
    packages: List[LockedPackage] = Field(default_factory=list)

    def package(self, address: str) -> Optional[LockedPackage]:
        """
        The locked package at the address, or nothing when the lock has none.
        """
        return next((package for package in self.packages if package.address == address), None)
