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


class ViewSavedCapability(TransactionCapability):
    """
    Keep the picture beside the annotation, in the documents of its dataset, named by the global id of the annotation, in place of the one it had.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "view_saved"
        ),
        version="1.0.0",
        name="View Saved",
        description="Keep the picture beside the annotation, in the documents of its dataset, named by the global id of the annotation.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "view", "persist"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The view was kept beside the annotation."},
            "debug_entry": {"en": "Working on: View Saved."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return AnnotationViewSaveProcessState.VIEW_SAVED.label(lang)

    def description(self, lang: str = "en") -> str:
        return AnnotationViewSaveProcessState.VIEW_SAVED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        guid: str = RequiredParameter.of(context, Request.GUID_KEY)
        container_path: Path = Path(RequiredParameter.of(context, Request.CONTAINER_KEY)).expanduser().resolve()
        data: bytes = AnnotationView.decode(RequiredParameter.of(context, Request.VIEW_KEY))

        path: Path = AnnotationStore(EntityWriteRequest.repository(context), container_path).view_path(guid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        context.set_parameter_value(Request.PATH_KEY, str(path.relative_to(container_path)) if path.is_relative_to(container_path) else str(path))

        return {
            "resulting_state": AnnotationViewSaveProcessState.VIEW_SAVED,
            "global_id": guid,
            "bytes": len(data),
        }
