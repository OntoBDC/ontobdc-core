from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.config_file import ConfigFile
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState


class ConfigOverriddenCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.config_overridden",
        version="1.0.0",
        name="Config Overridden",
        description="Copy the override of system.obdc, when it has one, to the override of the asset/config.yaml of the source folder of the container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "update", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Config Overridden."},
            "debug_entry": {"en": "Reaching the state Config Overridden."},
        },
    )

    # The configuration of the application, in the source folder of the container.
    CONFIG_PATH = Path("asset") / "config.yaml"
    KEY = "override"

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Configuração Sobrescrita"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # A system with no override has nothing to copy; one that has it is satisfied
        # when the config already says that same override.
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        if not descriptor.override:
            return True

        return ConfigFile.has(self._config(container_path, descriptor), self.KEY, descriptor.override)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        config: Path = self._config(container_path, descriptor)
        if descriptor.override:
            ConfigFile.copy(config, self.KEY, descriptor.override)

        return {
            "resulting_state": SystemInstallProcessState.CONFIG_OVERRIDDEN,
            "config": str(config),
            "overridden": bool(descriptor.override),
        }

    @classmethod
    def _config(cls, container_path: Path, descriptor: SystemDescriptor) -> Path:
        return container_path / descriptor.source.local / cls.CONFIG_PATH
