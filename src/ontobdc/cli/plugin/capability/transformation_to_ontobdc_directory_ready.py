from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import ensure_ontobdc_directory, get_init_root_path


class OntobdcDirectoryReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.ontobdc_directory_ready",
        version="1.0.0",
        name="OntoBDC Directory Ready",
        description="Ensure that the target directory contains the .__ontobdc__ directory.",
        author=["TRAE"],
        tags=["cli", "init", "bootstrap"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "OntoBDC Directory Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the .__ontobdc__ directory in the command target path."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = get_init_root_path(context=context)
        ontobdc_directory = ensure_ontobdc_directory(root_path)
        return {
            "resulting_state": CliInitProcessState.ONTOBDC_DIRECTORY_READY,
            "root_path": str(root_path),
            "ontobdc_directory": str(ontobdc_directory),
        }
