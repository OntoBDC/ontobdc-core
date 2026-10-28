from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState


class SourceRemoteRecordedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.source_remote_recorded",
        version="1.0.0",
        name="Source Remote Recorded",
        description="Record in system.obdc the GitHub repository the ddock was installed from.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Source Remote Recorded."},
            "debug_entry": {"en": "Reaching the state Source Remote Recorded."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Remote do Fonte Gravado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # An installation that names no repository has nothing to record.
        remote: Optional[str] = SystemInstallRequest.ddock_source(context)
        if remote is None:
            return True

        descriptor: SystemDescriptor = SystemDescriptors.read(SystemInstallRequest.container_path(context))
        return descriptor.source.remote == remote

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        remote: Optional[str] = SystemInstallRequest.ddock_source(context)
        if remote is None:
            return {
                "resulting_state": SystemInstallProcessState.SOURCE_REMOTE_RECORDED,
                "remote": "",
            }

        path: Path = SystemDescriptors.write_remote(container_path, remote)

        return {
            "resulting_state": SystemInstallProcessState.SOURCE_REMOTE_RECORDED,
            "remote": remote,
            "descriptor": str(path),
        }
