from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.system_lock import SystemLock

from ontobdc.ddock.domain.model.system_install import ArchiveFiles, LockedDdock, SystemLockContent

class SystemLockWrittenCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.system_lock_written",
        version="1.0.0",
        name="System Lock Written",
        description="Write the system.obdc.lock that says what was installed.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "System Lock Written."},
            "debug_entry": {"en": "Reaching the state System Lock Written."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Lock do Sistema Gravado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        return SystemLock.installed(container_path, descriptor)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        lock_path: Path = SystemLock.write(
            container_path,
            descriptor,
            self._ddock(context, descriptor),
            SystemInstallRequest.packages(context, descriptor.packages),
        )

        return {
            "resulting_state": SystemInstallProcessState.SYSTEM_LOCK_WRITTEN,
            "lock": str(lock_path),
        }

    @staticmethod
    def _ddock(context: CliContextPort, descriptor: SystemDescriptor) -> LockedDdock:
        """
        ddock as this installation unpacked it, or as the lock has it when an
        earlier installation did and the work folder is gone.
        """
        archive: Optional[ArchiveFiles] = SystemInstallRequest.fetched(SystemInstallRequest.ddock_path(context))
        if archive is not None:
            return LockedDdock(**archive.model_dump(), source=descriptor.source.local)

        lock: Optional[SystemLockContent] = SystemLock.read(SystemInstallRequest.container_path(context))
        if lock is None:
            raise FileNotFoundError("ddock was not unpacked and the container has no lock that says what it put there.")

        return lock.ddock
