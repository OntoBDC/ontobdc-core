from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.publication import gather_view_data, is_data_gathered
from ontobdc.view.domain.machine.state import ContainerViewProcessState


class DataGatheredCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "data_gathered"
        ),
        version="1.0.0",
        name="Data Gathered",
        description="Materialize the data consumed by the container view.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "view",
            "container",
            "publication",
            "data",
            "transformation",
        ],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerViewProcessState.DATA_GATHERED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerViewProcessState.DATA_GATHERED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        payload = gather_view_data(context)
        return {
            "resulting_state": ContainerViewProcessState.DATA_GATHERED,
            "container_path": payload["container"]["path"],
            "indexed_files": payload["summary"]["indexed_files"],
            "source_fingerprint": payload["source_fingerprint"],
            "options_fingerprint": payload["options_fingerprint"],
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return is_data_gathered(context)
