import json
from typing import Any, Dict, List, Optional

from ontobdc.context.adapter.repository import EntityAnalysisStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.learning_state import EntityAnalysisProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class AnalysedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.analysed",
        version="1.0.0",
        name="Context analysis transformation to Analysed",
        description="Choose the best candidate from the scored analysis payload.",
        author=["TRAE"],
        tags=["context", "analysis", "analysed", "vector"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Highest-scoring candidate was selected from the analysis "
                    "payload."
                ),
            },
            "debug_entry": {
                "en": (
                    "Selecting the highest-scoring candidate from the "
                    "analysis payload."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Context analysis transformation to Analysed"

    def description(self, lang: str = "en") -> str:
        return "Choose the best candidate from the scored analysis payload."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: EntityAnalysisStepRepository = context.get_parameter_value("step_repository")
        identified_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityAnalysisProcessState.IDENTIFIED).content)
        )
        scored_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityAnalysisProcessState.SCORED).content)
        )

        scored_candidates: List[Dict[str, Any]] = list(scored_payload.get("candidates", []))
        double_min_distance_threshold: Optional[float] = None
        relative_distance_threshold: float = 0.8
        remaining_max_distance: Optional[float] = None
        discarded_by_double_min_distance_candidates: List[Dict[str, Any]] = []
        discarded_by_relative_distance_candidates: List[Dict[str, Any]] = []
        filtered_candidates: List[Dict[str, Any]] = []
        best_match: Optional[Dict[str, Any]] = None

        if scored_candidates:
            normalized_candidates: List[Dict[str, Any]] = [
                {
                    "candidate_uri": str(candidate["candidate_uri"]),
                    "entity_type_uri": str(candidate.get("entity_type_uri", "")).strip(),
                    "distance": float(candidate["distance"]),
                    "vector": list(candidate["vector"]),
                }
                for candidate in scored_candidates
            ]

            minimum_distance: float = min(candidate["distance"] for candidate in normalized_candidates)
            double_min_distance_threshold = minimum_distance * 2.0
            surviving_double_min_distance_candidates: List[Dict[str, Any]] = []
            for candidate in normalized_candidates:
                if candidate["distance"] > double_min_distance_threshold:
                    discarded_by_double_min_distance_candidates.append(candidate)
                    continue
                surviving_double_min_distance_candidates.append(candidate)

            if surviving_double_min_distance_candidates:
                remaining_max_distance = max(
                    candidate["distance"] for candidate in surviving_double_min_distance_candidates
                )
                for candidate in surviving_double_min_distance_candidates:
                    relative_distance_ratio: float = (
                        0.0 if remaining_max_distance <= 0.0 else candidate["distance"] / remaining_max_distance
                    )
                    candidate_with_ratio: Dict[str, Any] = {
                        **candidate,
                        "relative_distance_ratio": relative_distance_ratio,
                    }
                    if relative_distance_ratio > relative_distance_threshold:
                        discarded_by_relative_distance_candidates.append(candidate_with_ratio)
                        continue
                    filtered_candidates.append(candidate_with_ratio)

            if filtered_candidates:
                best_match = min(filtered_candidates, key=lambda candidate: float(candidate["distance"]))

        analysed_payload: Dict[str, Any] = {
            "source_path": identified_payload["path"],
            "document": scored_payload["document"],
            "max_distance": float(scored_payload["max_distance"]),
            "candidate_count": int(scored_payload["candidate_count"]),
            "entity_count": int(scored_payload["entity_count"]),
            "entity_candidates_count": dict(scored_payload.get("entity_candidates_count", {})),
            "double_min_distance_threshold": double_min_distance_threshold,
            "relative_distance_threshold": relative_distance_threshold,
            "remaining_max_distance": remaining_max_distance,
            "discarded_by_double_min_distance_candidates": discarded_by_double_min_distance_candidates,
            "discarded_by_relative_distance_candidates": discarded_by_relative_distance_candidates,
            "filtered_candidate_count": len(filtered_candidates),
            "filtered_candidates": filtered_candidates,
            "best_match": (
                {
                    "candidate_uri": best_match["candidate_uri"],
                    "entity_type_uri": best_match["entity_type_uri"],
                    "distance": float(best_match["distance"]),
                    "vector": best_match["vector"],
                    "relative_distance_ratio": float(best_match["relative_distance_ratio"]),
                }
                if best_match is not None
                else None
            ),
            "accepted": best_match is not None,
        }

        analysed_path = step_repository.write_text_file(
            state=EntityAnalysisProcessState.ANALYSED,
            content=json.dumps(analysed_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(analysed_path))
        return {
            "resulting_state": EntityAnalysisProcessState.ANALYSED,
            "path": str(analysed_path),
        }
