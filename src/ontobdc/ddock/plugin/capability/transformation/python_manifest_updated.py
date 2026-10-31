from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.python_manifest import PythonManifest
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState


class PythonManifestUpdatedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.python_manifest_updated",
        version="1.0.0",
        name="Python Manifest Updated",
        description="Put the Python dependencies of system.obdc, with their versions, in the wheels of the python/manifest.json of the source folder of the container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "update", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Python Manifest Updated."},
            "debug_entry": {"en": "Reaching the state Python Manifest Updated."},
        },
    )

    MANIFEST_PATH = Path("python") / "manifest.json"

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Manifest Python Atualizado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # A source folder with no manifest has nothing to update.
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        manifest: Path = container_path / descriptor.source.local / self.MANIFEST_PATH
        return not manifest.is_file() or PythonManifest.is_updated(manifest, descriptor.python_dependencies)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        manifest: Path = container_path / descriptor.source.local / self.MANIFEST_PATH
        changed: List[str] = PythonManifest.update(manifest, descriptor.python_dependencies) if manifest.is_file() else []

        return {
            "resulting_state": SystemInstallProcessState.PYTHON_MANIFEST_UPDATED,
            "manifest": str(manifest),
            "wheels": changed,
        }
