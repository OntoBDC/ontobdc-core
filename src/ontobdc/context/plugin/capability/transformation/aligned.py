import json
import math
from collections import Counter
from typing import Any, Dict, List, Set, Tuple

from ontobdc.context.adapter.repository import EntityLearningStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.learning_state import EntityLearningProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class AlignedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.aligned",
        version="1.0.0",
        name="Context learning transformation to Aligned",
        description="Build a deterministic aligned vector from the spatialized learning source.",
        author=["TRAE"],
        tags=["context", "learning", "aligned"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context learning transformation to Aligned"

    def description(self, lang: str = "en") -> str:
        return "Build a deterministic aligned vector from the spatialized learning source."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import langid
        except ImportError as exc:
            raise ValueError("The 'langid' package is required to classify learning source language.") from exc

        step_repository: EntityLearningStepRepository = context.get_parameter_value("step_repository")
        spatialized_resource: LocalContextFileResource = step_repository.reload(EntityLearningProcessState.SPATIALIZED)
        spatialized_payload: Dict[str, Any] = json.loads(str(spatialized_resource.content))
        pages: List[Dict[str, Any]] = spatialized_payload["pages"]

        full_text: str = " ".join(str(page.get("text", "")) for page in pages)
        language_code, language_score = langid.classify(full_text)
        aligned_weight: List[float] = self._build_aligned_content(
            pages=pages,
            language_code=language_code,
        )

        aligned_payload: Dict[str, Any] = {
            "resource": dict(spatialized_payload["resource"]),
            "language": {
                "code": language_code,
                "score": float(language_score),
            },
            "weight": aligned_weight,
        }
        aligned_path = step_repository.write_text_file(
            state=EntityLearningProcessState.ALIGNED,
            content=json.dumps(aligned_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(aligned_path))
        return {
            "resulting_state": EntityLearningProcessState.ALIGNED,
            "path": str(aligned_path),
        }

    def _build_aligned_content(
        self,
        pages: List[Dict[str, Any]],
        language_code: str,
    ) -> List[float]:
        metadata: Dict[str, Any] = dict(pages[0].get("metadata", {}))
        boxes: List[Dict[str, Any]] = [
            box
            for page in pages
            for box in page.get("page_boxes", [])
            if isinstance(box, dict)
        ]
        full_text: str = " ".join(str(page.get("text", "")) for page in pages)
        top_words_count: int = self._top_words_count(
            text=full_text,
            language_code=language_code,
            top_percent=0.2,
        )
        features: List[float] = [
            float(metadata.get("page_count", len(pages))),
            float(sum(1 for box in boxes if box.get("class") == "section-header")),
            float(sum(1 for box in boxes if box.get("class") == "list-item")),
            float(top_words_count),
        ]
        max_vals: List[float] = [100.0, 50.0, 100.0, 10000.0]
        return [feature / max_value for feature, max_value in zip(features, max_vals)]

    def _top_words_count(self, text: str, language_code: str, top_percent: float) -> int:
        tokens: List[str] = self._tokenize(text=text, language_code=language_code)
        stopwords: Set[str] = self._stopwords(language_code=language_code)
        filtered_tokens: List[str] = [token for token in tokens if token not in stopwords]
        if not filtered_tokens:
            return 0

        frequencies: Counter[str] = Counter(filtered_tokens)
        unique_word_count: int = len(frequencies)
        top_k: int = max(1, int(math.ceil(unique_word_count * top_percent)))
        return sum(count for _, count in frequencies.most_common(top_k))

    def _tokenize(self, text: str, language_code: str) -> List[str]:
        doc = self._spacy_language(language_code=language_code).make_doc(text.lower())
        return [token.text for token in doc if token.is_alpha]

    def _stopwords(self, language_code: str) -> Set[str]:
        return set(self._spacy_language(language_code=language_code).Defaults.stop_words)

    def _spacy_language(self, language_code: str) -> Any:
        try:
            import spacy
        except ImportError as exc:
            raise ValueError("The 'spacy' package is required to build aligned learning vectors.") from exc

        normalized_code: str = language_code.lower().split("-", 1)[0].split("_", 1)[0]
        try:
            return spacy.blank(normalized_code)
        except Exception as exc:
            raise ValueError(f"Unsupported spaCy language code '{normalized_code}'.") from exc
