import hashlib
from importlib import metadata
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import ValidationError

from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.domain.model.system_install import (
    LockedDdock,
    LockedPackage,
    LockedPythonDependency,
    SystemLockContent,
    UnpackedPackage,
)


class SystemLock:
    """
    The ``system.obdc.lock`` of a project: what an installation put there, so
    that the same system can be told from another and installed again.
    """

    @classmethod
    def read(cls, project_path: Path) -> Optional[SystemLockContent]:
        """
        The content of the lock of the project, or nothing when it has none or it is not valid.
        """
        path: Path = project_path / SystemDescriptors.LOCK_FILE_NAME
        if not path.is_file():
            return None

        try:
            return SystemLockContent.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValidationError):
            return None

    @classmethod
    def ddock_complete(cls, project_path: Path, descriptor: SystemDescriptor) -> bool:
        """
        Whether the lock has the files of ddock and the project has all of them.
        """
        lock: Optional[SystemLockContent] = cls.read(project_path)
        if lock is None or lock.ddock.source != descriptor.source:
            return False

        return lock.ddock.present_in(project_path / descriptor.source)

    @classmethod
    def pending_packages(cls, project_path: Path, descriptor: SystemDescriptor) -> List[str]:
        """
        The packages of system.obdc that are not installed: those the lock
        does not have, and those that miss a file the lock says they put there.
        """
        lock: Optional[SystemLockContent] = cls.read(project_path)
        destination: Path = project_path / descriptor.source
        pending: List[str] = []
        address: str
        for address in descriptor.packages:
            locked: Optional[LockedPackage] = lock.package(address) if lock is not None else None
            if locked is None or not locked.present_in(destination):
                pending.append(address)

        return pending

    @classmethod
    def installed(cls, project_path: Path, descriptor: SystemDescriptor) -> bool:
        """
        Whether the lock is the one of this system.obdc and the project has
        every file of ddock and of the packages that it lists.
        """
        return (
            cls.descriptor_matches(project_path)
            and cls.ddock_complete(project_path, descriptor)
            and not cls.pending_packages(project_path, descriptor)
        )

    @classmethod
    def descriptor_matches(cls, project_path: Path) -> bool:
        """
        Whether the lock was written for the system.obdc as it is now.
        """
        lock: Optional[SystemLockContent] = cls.read(project_path)
        return lock is not None and lock.descriptor_sha256 == cls._descriptor_sha256(project_path)

    @classmethod
    def write(
        cls,
        project_path: Path,
        descriptor: SystemDescriptor,
        ddock: LockedDdock,
        installed_now: List[UnpackedPackage],
    ) -> Path:
        """
        Write the lock next to ``system.obdc``, and return where it is.

        The packages are those of system.obdc, in its order: the ones
        installed now and the ones an earlier installation had put there.
        """
        previous: Optional[SystemLockContent] = cls.read(project_path)
        packages: List[LockedPackage] = []
        address: str
        for address in descriptor.packages:
            now: Optional[UnpackedPackage] = next((package for package in installed_now if package.address == address), None)
            if now is not None:
                packages.append(LockedPackage(address=address, **now.archive.model_dump()))
                continue

            before: Optional[LockedPackage] = previous.package(address) if previous is not None else None
            if before is not None:
                packages.append(before)

        content: SystemLockContent = SystemLockContent(
            descriptor_sha256=cls._descriptor_sha256(project_path),
            python=[
                LockedPythonDependency(
                    name=dependency.name,
                    requested=dependency.version,
                    installed=metadata.version(dependency.name),
                )
                for dependency in descriptor.python_dependencies
            ],
            ddock=ddock,
            packages=packages,
        )
        path: Path = project_path / SystemDescriptors.LOCK_FILE_NAME
        path.write_text(yaml.safe_dump(content.model_dump(mode="json"), sort_keys=False, allow_unicode=True), encoding="utf-8")

        return path

    @staticmethod
    def _descriptor_sha256(project_path: Path) -> str:
        return hashlib.sha256(SystemDescriptors.path_in(project_path).read_bytes()).hexdigest()
