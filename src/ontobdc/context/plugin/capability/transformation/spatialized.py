import json
from typing import Any, Dict, List

from ontobdc.context.adapter.repository import EntityLearningStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.learning_state import EntityLearningProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class SpatializedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.spatialized",
        version="1.0.0",
        name="Context learning transformation to Spatialized",
        description="Extract page chunks and bounding boxes from the identified learning source.",
        author=["TRAE"],
        tags=["context", "learning", "spatialized"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context learning transformation to Spatialized"

    def description(self, lang: str = "en") -> str:
        return "Extract page chunks and bounding boxes from the identified learning source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise ValueError("The 'pymupdf4llm' package is required to spatialize PDF learning sources.") from exc

        step_repository: EntityLearningStepRepository = context.get_parameter_value("step_repository")
        identified_resource: LocalContextFileResource = step_repository.reload(EntityLearningProcessState.IDENTIFIED)
        identified_payload: Dict[str, Any] = json.loads(str(identified_resource.content))
        source_resource = LocalContextFileResource(identified_payload["path"])

        spatialized_pages: List[Dict[str, Any]] = pymupdf4llm.to_markdown(
            str(source_resource.path),
            page_chunks=True,
            extract_words=True,
        )
        if not spatialized_pages:
            raise ValueError(f"Could not spatialize resource '{source_resource.path}'.")

        spatialized_payload: Dict[str, Any] = {
            "resource": source_resource.to_json(),
            "pages": spatialized_pages,
        }
        spatialized_path = step_repository.write_text_file(
            state=EntityLearningProcessState.SPATIALIZED,
            content=json.dumps(spatialized_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(spatialized_path))
        return {
            "resulting_state": EntityLearningProcessState.SPATIALIZED,
            "path": str(spatialized_path),
        }
