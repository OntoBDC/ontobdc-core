import json
from typing import Any, Dict

from ontobdc.context.adapter.repository import EntityAnalysisStepRepository, LocalContextFileResource
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.context.domain.machine.learning_state import EntityAnalysisProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class VectorsLoadedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.vectors_loaded",
        version="1.0.0",
        name="Context analysis transformation to Vectors Loaded",
        description="Load registered vector candidates for the analysis flow.",
        author=["TRAE"],
        tags=["context", "analysis", "vector", "loaded"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context analysis transformation to Vectors Loaded"

    def description(self, lang: str = "en") -> str:
        return "Load registered vector candidates for the analysis flow."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: EntityAnalysisStepRepository = context.get_parameter_value("step_repository")
        vector_repository = EntityVectorRepositoryAdapter(root_path=str(context.root_path))
        origins_resource: LocalContextFileResource = step_repository.reload(
            EntityAnalysisProcessState.ORIGIN_RESOLVED
        )
        origins_payload: Dict[str, Any] = json.loads(str(origins_resource.content))
        loaded_payload: Dict[str, Any] = vector_repository.load_registered_candidates(
            file_paths=list(origins_payload["vector_files"])
        )
        if loaded_payload["candidate_count"] <= 0:
            raise ValueError("No registered vector candidates could be loaded from the resolved sources.")

        output_path = step_repository.write_text_file(
            state=EntityAnalysisProcessState.VECTORS_LOADED,
            content=json.dumps(loaded_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(output_path))
        return {
            "resulting_state": EntityAnalysisProcessState.VECTORS_LOADED,
            "path": str(output_path),
        }
