from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.python_dependencies import PythonDependencies


class PythonDependenciesInstalledCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.python_dependencies_installed",
        version="1.0.0",
        name="Python Dependencies Installed",
        description="Install the Python dependencies of system.obdc, at the versions it asks for.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Python Dependencies Installed."},
            "debug_entry": {"en": "Reaching the state Python Dependencies Installed."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Dependências Python Instaladas"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        descriptor: SystemDescriptor = SystemDescriptors.read(SystemInstallRequest.project_path(context))
        return PythonDependencies.satisfied(descriptor.python_dependencies)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        descriptor: SystemDescriptor = SystemDescriptors.read(SystemInstallRequest.project_path(context))
        installed: Dict[str, str] = PythonDependencies.install(descriptor.python_dependencies)

        return {
            "resulting_state": SystemInstallProcessState.PYTHON_DEPENDENCIES_INSTALLED,
            "installed": installed,
        }
