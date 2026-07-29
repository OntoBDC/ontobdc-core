
import json
from typing import Any, Dict
from ontobdc.context.adapter.repository import EntityAnalysisStepRepository, LocalContextFileResource
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.context.domain.machine.learning_state import EntityAnalysisProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class OriginResolvedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.origin_resolved",
        version="1.0.0",
        name="Context analysis transformation to Origin Resolved",
        description="Resolve the registered vector sources for the analysis flow.",
        author=["TRAE"],
        tags=["context", "analysis", "vector", "origin"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context analysis transformation to Origin Resolved"

    def description(self, lang: str = "en") -> str:
        return "Resolve the registered vector sources for the analysis flow."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Resolve and materialize the vector origins used by the analysis pipeline.

        This step is intentionally a discovery/materialization step, not the place
        where RDF vectors are parsed yet. Its job is to:

        1. Read the active project root from the execution context.
        2. Instantiate the vector repository adapter for that root.
        3. Synchronize remote `vector.ttl` files from the fixed Brasidata ontology
           commit into `[root]/.__ontobdc__/cache/ontology/...`.
        4. Ask the adapter to discover registered local `vector.ttl` sources under
           the project tree, excluding transient files under `.__ontobdc__`, and
           also include cached ontology vectors under `.__ontobdc__/cache/ontology`.
        5. Enforce the minimum contract of the analysis flow: there must be at least
           one registered vector source available, otherwise the analysis cannot proceed.
        6. Persist the resolved origin snapshot as the artifact for the
           `__origin_resolved__` state so later capabilities consume a stable input
           instead of rediscovering files ad hoc.

        The resulting JSON payload is deliberately simple: it is a serialized
        snapshot of vector source locations, not yet the loaded candidate vectors.
        The actual RDF loading/parsing happens only in subsequent states.
        """
        step_repository: EntityAnalysisStepRepository = context.get_parameter_value("step_repository")
        vector_repository = EntityVectorRepositoryAdapter(root_path=str(context.root_path))
        remote_cache_payload: Dict[str, Any] = vector_repository.sync_remote_ontology_vector_cache()
        origins_payload: Dict[str, Any] = vector_repository.resolve_origins()
        origins_payload["remote_cache"] = remote_cache_payload
        if not origins_payload["vector_files"]:
            raise ValueError("No registered vector.ttl files were found under the project root.")

        output_path = step_repository.write_text_file(
            state=EntityAnalysisProcessState.ORIGIN_RESOLVED,
            content=json.dumps(origins_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(output_path))
        return {
            "resulting_state": EntityAnalysisProcessState.ORIGIN_RESOLVED,
            "path": str(output_path),
        }
