from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState


class SystemDescriptorValidCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.system_descriptor_valid",
        version="1.0.0",
        name="System Descriptor Valid",
        description="Confirm that the container has a system.obdc and that it is valid.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "System Descriptor Valid."},
            "debug_entry": {"en": "Reaching the state System Descriptor Valid."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Descritor do Sistema Válido"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        try:
            SystemDescriptors.read(SystemInstallRequest.container_path(context))
        except Exception:
            return False

        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)

        return {
            "resulting_state": SystemInstallProcessState.SYSTEM_DESCRIPTOR_VALID,
            "source": descriptor.source.local,
            "remote": descriptor.source.remote,
            "python_dependencies": [dependency.requirement() for dependency in descriptor.python_dependencies],
            "packages": descriptor.packages,
        }
