from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.adapter.store import AnnotationStore
from ontobdc.annotate.domain.model.view import AnnotationView
from ontobdc.annotate.plugin.machine.annotation_view_save.port import AnnotationViewSaveRequestPort as Request
from ontobdc.annotate.plugin.machine.annotation_view_save.state import AnnotationViewSaveProcessState


class ViewRequestedCapability(TransactionCapability):
    """
    Check that the annotation exists and that what is given as its view is the picture of one.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "view_requested"
        ),
        version="1.0.0",
        name="View Requested",
        description="Check that the annotation exists and that what is given as its view is the picture of one.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "view", "picture"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The view asked for on the annotation was understood."},
            "debug_entry": {"en": "Working on: View Requested."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return AnnotationViewSaveProcessState.VIEW_REQUESTED.label(lang)

    def description(self, lang: str = "en") -> str:
        return AnnotationViewSaveProcessState.VIEW_REQUESTED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        guid: str = RequiredParameter.of(context, Request.GUID_KEY)
        container_path: Path = Path(RequiredParameter.of(context, Request.CONTAINER_KEY)).expanduser().resolve()

        # The annotation has to be there before a picture is kept for it.
        AnnotationStore(EntityWriteRequest.repository(context), container_path).row(guid)
        AnnotationView.decode(RequiredParameter.of(context, Request.VIEW_KEY))

        return {
            "resulting_state": AnnotationViewSaveProcessState.VIEW_REQUESTED,
            "annotation_guid": guid,
        }
