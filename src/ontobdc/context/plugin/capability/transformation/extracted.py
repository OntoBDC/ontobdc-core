import json
from typing import Any, Dict

from ontobdc.context.adapter.repository import EntityLearningStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.learning_state import EntityLearningProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class ExtractedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.extracted",
        version="1.0.0",
        name="Context learning transformation to Extracted",
        description="Extract text content from the identified learning source.",
        author=["TRAE"],
        tags=["context", "learning", "extracted"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context learning transformation to Extracted"

    def description(self, lang: str = "en") -> str:
        return "Extract text content from the identified learning source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise ValueError("The 'pymupdf4llm' package is required to extract PDF learning sources.") from exc

        step_repository: EntityLearningStepRepository = context.get_parameter_value("step_repository")
        identified_resource: LocalContextFileResource = step_repository.reload(EntityLearningProcessState.IDENTIFIED)
        identified_payload: Dict[str, Any] = json.loads(str(identified_resource.content))
        source_resource = LocalContextFileResource(identified_payload["path"])
        if source_resource.mimetype != "application/pdf":
            raise ValueError(
                f"Entity learning currently supports only PDF sources. Got '{source_resource.mimetype}'."
            )

        extracted_content: str = pymupdf4llm.to_markdown(str(source_resource.path))
        if not extracted_content.strip():
            raise ValueError(f"Could not extract text content from '{source_resource.path}'.")

        extracted_path = step_repository.write_text_file(
            state=EntityLearningProcessState.EXTRACTED,
            content=extracted_content,
            file_type="md",
        )
        context.set_parameter_value("resource", LocalContextFileResource(extracted_path))
        return {
            "resulting_state": EntityLearningProcessState.EXTRACTED,
            "path": str(extracted_path),
        }
