from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.node_build import NodeBuild


class NodeBuiltCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.node_built",
        version="1.0.0",
        name="Node Built",
        description="Install the npm dependencies and compile the node application with npm run build.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Node Built."},
            "debug_entry": {"en": "Reaching the state Node Built."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Node Compilado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # A build is not a fact kept on disk: the sources can have changed, so
        # each run builds once, and only this run's build counts.
        return context.get_parameter_value(SystemInstallRequest.BUILT_KEY) is True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = SystemInstallRequest.project_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(project_path)
        NodeBuild.run(project_path / descriptor.source)
        context.set_parameter_value(SystemInstallRequest.BUILT_KEY, True)

        return {
            "resulting_state": SystemInstallProcessState.NODE_BUILT,
            "command": NodeBuild.COMMAND_TEXT,
        }
