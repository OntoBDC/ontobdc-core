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
    The ``system.obdc.lock`` of a container: what an installation put there, so
    that the same system can be told from another and installed again.
    """

    @classmethod
    def read(cls, container_path: Path) -> Optional[SystemLockContent]:
        """
        The content of the lock of the container, or nothing when it has none or it is not valid.
        """
        path: Path = container_path / SystemDescriptors.LOCK_FILE_NAME
        if not path.is_file():
            return None

        try:
            return SystemLockContent.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValidationError):
            return None

    @classmethod
    def ddock_complete(cls, container_path: Path, descriptor: SystemDescriptor) -> bool:
        """
        Whether the lock has the files of ddock and the container has all of them.
        """
        lock: Optional[SystemLockContent] = cls.read(container_path)
        if lock is None or lock.ddock.source != descriptor.source.local:
            return False

        return lock.ddock.present_in(container_path / descriptor.source.local)

    @classmethod
    def pending_packages(cls, container_path: Path, descriptor: SystemDescriptor) -> List[str]:
        """
        The packages of system.obdc that are not installed: those the lock
        does not have, and those that miss a file the lock says they put there.
        """
        lock: Optional[SystemLockContent] = cls.read(container_path)
        destination: Path = container_path / descriptor.source.local
        pending: List[str] = []
        address: str
        for address in descriptor.packages:
            locked: Optional[LockedPackage] = lock.package(address) if lock is not None else None
            if locked is None or not locked.present_in(destination):
                pending.append(address)

        return pending

    @classmethod
    def installed(cls, container_path: Path, descriptor: SystemDescriptor) -> bool:
        """
        Whether the lock is the one of this system.obdc and the container has
        every file of ddock and of the packages that it lists.
        """
        return (
            cls.descriptor_matches(container_path)
            and cls.ddock_complete(container_path, descriptor)
            and not cls.pending_packages(container_path, descriptor)
        )

    @classmethod
    def descriptor_matches(cls, container_path: Path) -> bool:
        """
        Whether the lock was written for the system.obdc as it is now.
        """
        lock: Optional[SystemLockContent] = cls.read(container_path)
        return lock is not None and lock.descriptor_sha256 == cls._descriptor_sha256(container_path)

    @classmethod
    def write(
        cls,
        container_path: Path,
        descriptor: SystemDescriptor,
        ddock: LockedDdock,
        installed_now: List[UnpackedPackage],
    ) -> Path:
        """
        Write the lock next to ``system.obdc``, and return where it is.

        The packages are those of system.obdc, in its order: the ones
        installed now and the ones an earlier installation had put there.
        """
        previous: Optional[SystemLockContent] = cls.read(container_path)
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
            descriptor_sha256=cls._descriptor_sha256(container_path),
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
        path: Path = container_path / SystemDescriptors.LOCK_FILE_NAME
        path.write_text(yaml.safe_dump(content.model_dump(mode="json"), sort_keys=False, allow_unicode=True), encoding="utf-8")

        return path

    @staticmethod
    def _descriptor_sha256(container_path: Path) -> str:
        return hashlib.sha256(SystemDescriptors.path_in(container_path).read_bytes()).hexdigest()
