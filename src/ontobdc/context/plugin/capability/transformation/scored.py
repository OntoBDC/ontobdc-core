import json
from typing import Any, Dict, List

from ontobdc.context.adapter.repository import EntityAnalysisStepRepository, LocalContextFileResource
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.context.domain.machine.learning_state import EntityAnalysisProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class ScoredCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.scored",
        version="1.0.0",
        name="Context analysis transformation to Scored",
        description="Score loaded vector candidates against the aligned file vector.",
        author=["TRAE"],
        tags=["context", "analysis", "scored", "vector"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context analysis transformation to Scored"

    def description(self, lang: str = "en") -> str:
        return "Score loaded vector candidates against the aligned file vector."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: EntityAnalysisStepRepository = context.get_parameter_value("step_repository")
        vector_repository = EntityVectorRepositoryAdapter(root_path=str(context.root_path))

        identified_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityAnalysisProcessState.IDENTIFIED).content)
        )
        aligned_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityAnalysisProcessState.ALIGNED).content)
        )
        loaded_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityAnalysisProcessState.VECTORS_LOADED).content)
        )

        document_vector: List[float] = [float(value) for value in aligned_payload["weight"]]
        supported_file_type: str = str(identified_payload["mimetype"]).strip()
        max_distance_raw: Any = loaded_payload.get("max_distance")
        max_distance: float = (
            float(max_distance_raw)
            if max_distance_raw is not None
            else float(vector_repository.default_max_distance)
        )

        scored_candidates: List[Dict[str, Any]] = []
        above_max_distance_candidates: List[Dict[str, Any]] = []
        entity_candidates_count: Dict[str, int] = {}
        for candidate in list(loaded_payload.get("candidates", [])):
            candidate_vector: List[float] = [float(value) for value in list(candidate.get("vector", []))]
            if len(candidate_vector) != len(document_vector):
                continue

            candidate_supported_file_type: str = str(candidate.get("supported_file_type", "")).strip()
            if candidate_supported_file_type and candidate_supported_file_type != supported_file_type:
                continue

            distance: float = self._euclidean_distance(document_vector, candidate_vector)
            if distance > max_distance:
                above_max_distance_candidates.append(
                    {
                        "candidate_uri": str(candidate["candidate_uri"]),
                        "entity_type_uri": str(candidate.get("entity_type_uri", "")).strip(),
                        "distance": distance,
                        "vector": candidate_vector,
                    }
                )
                continue

            entity_type_uri: str = str(candidate.get("entity_type_uri", "")).strip()
            entity_count_key: str = entity_type_uri or str(candidate["candidate_uri"]).strip()
            entity_candidates_count[entity_count_key] = entity_candidates_count.get(entity_count_key, 0) + 1

            scored_candidates.append(
                {
                    "candidate_uri": str(candidate["candidate_uri"]),
                    "entity_type_uri": entity_type_uri,
                    "distance": distance,
                    "vector": candidate_vector,
                }
            )

        scored_candidates.sort(key=lambda candidate: (float(candidate["distance"]), str(candidate["candidate_uri"])))
        above_max_distance_candidates.sort(
            key=lambda candidate: (float(candidate["distance"]), str(candidate["candidate_uri"]))
        )

        scored_payload: Dict[str, Any] = {
            "source_path": identified_payload["path"],
            "document": {
                "supported_file_type": supported_file_type,
                "content_language": aligned_payload["language"]["code"],
                "language_score": float(aligned_payload["language"]["score"]),
                "vector": document_vector,
            },
            "max_distance": max_distance,
            "candidate_count": len(scored_candidates),
            "entity_count": len(entity_candidates_count),
            "entity_candidates_count": dict(sorted(entity_candidates_count.items())),
            "above_max_distance_candidates": above_max_distance_candidates,
            "candidates": scored_candidates,
        }

        output_path = step_repository.write_text_file(
            state=EntityAnalysisProcessState.SCORED,
            content=json.dumps(scored_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(output_path))
        return {
            "resulting_state": EntityAnalysisProcessState.SCORED,
            "path": str(output_path),
        }

    def _euclidean_distance(self, a: List[float], b: List[float]) -> float:
        return float(sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5)
