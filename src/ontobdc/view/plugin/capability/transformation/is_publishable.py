from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.publication import ensure_publishable
from ontobdc.view.adapter.publishability import is_container_publishable
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState


class IsPublishableCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "is_publishable"
        ),
        version="1.0.0",
        name="Is Publishable",
        description=(
            "Synchronize and validate the container publication descriptor."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "container", "publication", "surface", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container publication descriptor was synchronized and validated "
                    "for Surface publication."
                ),
            },
            "debug_entry": {
                "en": (
                    "Synchronizing and validating the container publication "
                    "descriptor for Surface publication."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.IS_PUBLISHABLE.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.IS_PUBLISHABLE.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return is_container_publishable(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = ensure_publishable(context)
        result["resulting_state"] = SurfaceGenerationProcessState.IS_PUBLISHABLE
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
