"""Evaluate a bare filename against keyword combinations using embeddings.

This is the first classification stage only. It does not inspect paths,
file contents, directory names or extension-derived MIME types.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from functools import lru_cache
from typing import Any, Callable, ClassVar, Dict, List, Optional, Sequence, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata

EmbeddingFunction = Callable[[Sequence[str]], Sequence[Sequence[float]]]


@lru_cache(maxsize=2)
def _load_embedding_model(model_name: str) -> Any:
    """Load a local/cacheable model on demand, not during plugin discovery."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "File-name similarity requires an embedding function or the "
            "optional 'sentence-transformers' package."
        ) from exc
    return SentenceTransformer(model_name)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return raw cosine similarity, bounded to [-1, 1]."""
    if len(left) == 0 or len(left) != len(right):
        raise ValueError("Embedding vectors must be non-empty and equal-sized.")
    a = [float(x) for x in left]
    b = [float(x) for x in right]
    if not all(math.isfinite(x) for x in a + b):
        raise ValueError("Embedding vectors must contain only finite values.")
    anorm = math.sqrt(math.fsum(x * x for x in a))
    bnorm = math.sqrt(math.fsum(x * x for x in b))
    if anorm == 0.0 or bnorm == 0.0:
        raise ValueError("Zero embedding vectors cannot be compared.")
    score = math.fsum(x * y for x, y in zip(a, b)) / (anorm * bnorm)
    return max(-1.0, min(1.0, score))


class FileNameSimilarityEvaluatedCapability(TransformationCapability):
    """Score keyword combinations against a filename; accept only above 0.85.

    Inputs are read from the CLI context. keyword_groups is JSON, e.g.:
    {"document_type": ["QuickSpecs", "Product Brief"],
     "equipment": ["server", "SSD"]}

    All (bounded) Cartesian combinations are evaluated. The returned ranking
    is evidence, not a calibrated probability. No records are persisted by
    this transformation; downstream ETL decides how/where to store the scores.
    """

    FILE_NAME_KEY: ClassVar[str] = "file_name"
    KEYWORD_GROUPS_KEY: ClassVar[str] = "keyword_groups"
    EMBEDDING_MODEL_KEY: ClassVar[str] = "embedding_model"
    MIN_SCORE: ClassVar[float] = 0.85
    MAX_COMBINATIONS: ClassVar[int] = 4096
    DEFAULT_MODEL: ClassVar[str] = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation."
            "file_name_similarity_evaluated"
        ),
        version="1.0.0",
        name="File Name Similarity Evaluated",
        description=(
            "Compare a bare filename with combinations of taxonomy keywords "
            "using embedding cosine similarity; return all scores and accept "
            "the best candidate only when similarity exceeds 0.85."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ontobdc", "context", "filename", "embedding", "classification"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                FILE_NAME_KEY: {"type": "string", "required": True},
                KEYWORD_GROUPS_KEY: {
                    "type": "string",
                    "required": True,
                    "description": "JSON object mapping group labels to string arrays.",
                },
                EMBEDDING_MODEL_KEY: {"type": "string", "required": False},
            },
        },
        output_schema={
            "properties": {
                "file_name": {"type": "string"},
                "normalized_name": {"type": "string"},
                "model": {"type": "string"},
                "metric": {"type": "string"},
                "threshold": {"type": "number"},
                "accepted": {"type": "boolean"},
                "classification": {"type": "object"},
                "best_match": {"type": "object"},
                "ranking": {"type": "array"},
            },
        },
        log_message={
            "info": {
                "en": "File-name similarity evaluated.",
                "pt-br": "Similaridade do nome do arquivo avaliada.",
            },
            "debug_entry": {
                "en": "Comparing the filename with keyword combinations.",
                "pt-br": "Comparando o nome com combinações de palavras-chave.",
            },
        },
    )

    def __init__(self, embedder: Optional[EmbeddingFunction] = None) -> None:
        # Optional injection enables offline models, custom model providers,
        # and isolated unit tests without an external model download.
        self._embedder = embedder

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Similaridade do nome do arquivo avaliada"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Classifica nomes de arquivos por similaridade com palavras-chave."
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        file_name = RequiredParameter.of(context, self.FILE_NAME_KEY)
        if "/" in file_name or "\\" in file_name or file_name in (".", ".."):
            raise ValueError("file_name must contain only a filename, never a path.")

        # Strip the extension and transform separators into whitespace without
        # trying to decode product IDs, abbreviations, or naming conventions.
        stem = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
        normalized_name = re.sub(r"[_\s]+", " ", stem).strip()
        if not normalized_name:
            raise ValueError("file_name has no usable text before the extension.")

        raw_groups = RequiredParameter.of(context, self.KEYWORD_GROUPS_KEY)
        try:
            groups = json.loads(raw_groups)
        except json.JSONDecodeError as exc:
            raise ValueError("keyword_groups must be valid JSON.") from exc
        if not isinstance(groups, dict) or not groups:
            raise ValueError("keyword_groups must be a non-empty JSON object.")

        group_names: List[str] = []
        group_values: List[List[str]] = []
        combinations_count = 1
        for group, keywords in groups.items():
            if not isinstance(group, str) or not group.strip():
                raise ValueError("Keyword group names must be non-empty strings.")
            if not isinstance(keywords, list) or not keywords or not all(
                isinstance(k, str) and k.strip() for k in keywords
            ):
                raise ValueError(f"Group '{group}' must contain non-empty strings.")
            group_names.append(group)
            group_values.append([k.strip() for k in keywords])
            combinations_count *= len(keywords)
            if combinations_count > self.MAX_COMBINATIONS:
                raise ValueError(
                    f"Too many keyword combinations (maximum {self.MAX_COMBINATIONS})."
                )

        combinations: List[Tuple[str, ...]] = list(itertools.product(*group_values))
        candidate_texts: List[str] = [" ".join(parts) for parts in combinations]
        model_name = (
            RequiredParameter.optional(context, self.EMBEDDING_MODEL_KEY)
            or self.DEFAULT_MODEL
        )
        embed: EmbeddingFunction = self._embedder or _load_embedding_model(model_name).encode
        embeddings = list(embed([normalized_name, *candidate_texts]))
        if len(embeddings) != 1 + len(combinations):
            raise ValueError("Embedding provider returned an unexpected vector count.")

        query_embedding = embeddings[0]
        ranking: List[Dict[str, Any]] = []
        for terms, expression, vector in zip(
            combinations, candidate_texts, embeddings[1:]
        ):
            ranking.append(
                {
                    "expression": expression,
                    "keywords": dict(zip(group_names, terms)),
                    "score": _cosine_similarity(query_embedding, vector),
                }
            )
        ranking.sort(key=lambda item: (-item["score"], item["expression"]))
        best = ranking[0]
        accepted = best["score"] > self.MIN_SCORE
        return {
            "file_name": file_name,
            "normalized_name": normalized_name,
            "model": model_name if self._embedder is None else "injected",
            "metric": "cosine_similarity",  # range [-1, 1], not probability
            "threshold": self.MIN_SCORE,
            "accepted": accepted,
            "classification": best["keywords"] if accepted else None,
            "best_match": best,
            "ranking": ranking,
        }
