from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment.plan import AttachmentPlanner
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class IdentityResolvedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "identity_resolved"
        ),
        version="1.0.0",
        name="Identity Resolved",
        description=(
            "Calculate target local identities and reject storage conflicts."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Local container and dataset identities were resolved after "
                    "storage conflicts were rejected."
                ),
            },
            "debug_entry": {
                "en": (
                    "Resolving local container and dataset identities after "
                    "rejecting storage conflicts."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.IDENTITY_RESOLVED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.IDENTITY_RESOLVED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = AttachmentPlanner(context).resolve_identity()
        result["resulting_state"] = (
            ContainerAttachProcessState.IDENTITY_RESOLVED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return AttachmentPlanner(context).is_identity_resolved()
