import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import (
    FileMeaningSuggestionProcessState,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.etl import (
    EtlDirectoryContract,
    EtlEventContextKeys,
    EtlEventPayloadKeys,
)
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate import ContainerRoCrate

from ontobdc.context.plugin.capability.transformation.ontology_terms_matched import (
    _LabelNormalizer,
    _OntologyTermExtractor,
)

ETL_MODULE_NAME: str = "context"
ETL_PHASE_NAME: str = "suggestion"
ETL_ENTITY_NAME: str = "file"


class _FuzzySubstringScorer:
    """Fuzzy substring enrichment scorer (state-11).

    Only operates on chunks that produced ZERO exact matches in state-10.
    For every ontology term whose NORMALIZED label is a SUBSTRING of the
    chunk lemma (or vice-versa), a score in (0, 1) is produced:

        score = len(shorter_string) / len(longer_string)

    which the user defines as: "percentage of the characters of the
    fuzzy-substring relative to the full term". Values close to 1.0
    indicate near-equality; values near 0.0 are very-short containment.
    """

    VERSION: ClassVar[str] = "fuzzy-substring-length-ratio-1.0.0"
    TOP_N_PER_CHUNK: ClassVar[int] = 5
    MINIMUM_FINAL_SCORE: ClassVar[float] = 0.2

    @classmethod
    def configuration(cls) -> Dict[str, Any]:
        return {
            "scoring_version": cls.VERSION,
            "top_n_per_chunk": cls.TOP_N_PER_CHUNK,
            "minimum_final_score": cls.MINIMUM_FINAL_SCORE,
            "score_rule": "min(len(normalized_a), len(normalized_b)) / max(len(normalized_a), len(normalized_b)), iff either normalized string contains the other",
        }

    @classmethod
    def _normalized_length_ratio(
        cls,
        *,
        a_normalized: str,
        b_normalized: str,
    ) -> Optional[float]:
        if not a_normalized or not b_normalized:
            return None
        if a_normalized == b_normalized:
            return 1.0
        if a_normalized in b_normalized or b_normalized in a_normalized:
            a_len: int = len(a_normalized)
            b_len: int = len(b_normalized)
            denom: int = max(a_len, b_len)
            if denom < 1:
                return None
            return float(min(a_len, b_len)) / float(denom)
        return None

    @classmethod
    def enrich_chunk(
        cls,
        *,
        lemma: str,
        language: str,
        chunk_id: Any,
        ontology_terms: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        lemma_clean: str = lemma.strip()
        if not lemma_clean:
            return [], 0
        language_clean: str = language.strip().lower().replace("_", "-")
        lemma_norm: str = _LabelNormalizer.normalize(lemma_clean)
        if not lemma_norm:
            return [], 0
        scored: List[Dict[str, Any]] = []
        seen_iris: Set[str] = set()
        term: Dict[str, Any]
        for term in ontology_terms:
            iri_raw: Any = term.get("iri")
            if not isinstance(iri_raw, str) or not iri_raw.strip():
                continue
            labels_raw: Any = term.get("labels")
            if isinstance(labels_raw, list):
                flat_labels: List[Tuple[str, str]] = []
                entry: Any
                for entry in labels_raw:
                    if not isinstance(entry, dict):
                        continue
                    lt: Any = entry.get("label")
                    ll: Any = entry.get("language")
                    if isinstance(lt, str) and lt.strip():
                        flat_labels.append((
                            lt.strip(),
                            (ll.strip().lower().replace("_", "-")
                             if isinstance(ll, str) and ll.strip()
                             else ""),
                        ))
            elif isinstance(labels_raw, dict):
                flat_labels = []
                lang_key: Any
                label_values: Any
                for lang_key, label_values in labels_raw.items():
                    if not isinstance(label_values, list):
                        continue
                    lang_clean: str = (
                        str(lang_key).strip().lower().replace("_", "-")
                        if isinstance(lang_key, str) and lang_key.strip()
                        else ""
                    )
                    for one_label in label_values:
                        if isinstance(one_label, str) and one_label.strip():
                            flat_labels.append((one_label.strip(), lang_clean))
            else:
                continue
            if not flat_labels:
                continue
            term_type_raw: Any = term.get("term_type")
            ontology_prefix_raw: Any = term.get("ontology_prefix")
            best_for_term: Optional[Dict[str, Any]] = None
            best_score_for_term: float = 0.0
            label_text: str
            label_lang_clean: str
            for label_text, label_lang_clean in flat_labels:
                if label_lang_clean:
                    if language_clean == "pt-br":
                        if label_lang_clean not in {"pt-br", "pt", "en"}:
                            continue
                    elif language_clean == "pt":
                        if label_lang_clean not in {"pt", "pt-br", "en"}:
                            continue
                    elif (
                        label_lang_clean != language_clean
                        and label_lang_clean != "en"
                    ):
                        continue
                label_norm: str = _LabelNormalizer.normalize(label_text)
                if not label_norm:
                    continue
                ratio: Optional[float] = cls._normalized_length_ratio(
                    a_normalized=lemma_norm,
                    b_normalized=label_norm,
                )
                if ratio is None:
                    continue
                if ratio < cls.MINIMUM_FINAL_SCORE:
                    continue
                if ratio <= best_score_for_term and best_for_term is not None:
                    continue
                best_score_for_term = ratio
                best_for_term = {
                    "text": label_text,
                    "language": label_lang_clean,
                    "score": ratio,
                }
            if best_for_term is None:
                continue
            if iri_raw in seen_iris:
                continue
            seen_iris.add(iri_raw)
            label_display: str = str(best_for_term["text"])
            score_value: float = float(best_for_term["score"])
            scored.append(
                {
                    "category_iri": iri_raw.strip(),
                    "category_label": label_display,
                    "ontology_prefix": (
                        ontology_prefix_raw
                        if isinstance(ontology_prefix_raw, str)
                        else ""
                    ),
                    "term_type": (
                        term_type_raw if isinstance(term_type_raw, str) else ""
                    ),
                    "score": score_value,
                    "score_rule": "fuzzy_substring_length_ratio",
                    "matched_term_label": label_display,
                    "matched_term_language": best_for_term["language"],
                }
            )
        scored.sort(
            key=lambda item: (
                -float(item["score"]),
                str(item.get("ontology_prefix", "")),
                str(item.get("category_label", "")),
            )
        )
        total_candidates: int = len(scored)
        top_n: int = max(1, int(cls.TOP_N_PER_CHUNK))
        return scored[:top_n], total_candidates


class FuzzyCategoryCandidatesEnrichedCapability(TransactionCapability):
    """State-11 of the file-meaning suggestion pipeline.

    Reads the exact-only category candidates produced by state-10
    (CATEGORY_CANDIDATES_FOUND) and performs a secondary fuzzy-substring
    enrichment **only on chunks that produced ZERO exact matches. The
    event does NOT re-replicate the entire upstream ontology_matches JSON; it
    reads the label universe directly from the central
    ``_OntologyTermExtractor`` adapter and returns only the newly
    produced fuzzy candidates.
    """

    EXACT_CANDIDATES_KEY: ClassVar[str] = "category_candidates"
    FUZZY_CANDIDATES_KEY: ClassVar[str] = "fuzzy_category_candidates"
    ITEMS_KEY: ClassVar[str] = "items"
    CHUNK_ID_KEY: ClassVar[str] = "chunk_id"
    CHUNKS_KEY: ClassVar[str] = "chunks"
    STATE_NAME: ClassVar[str] = "fuzzy_category_candidates_enriched"
    EXACT_SCORING_VERSION_KEY: ClassVar[str] = "category-scoring-version"
    EXACT_SCORING_VERSION: ClassVar[str] = "1.0.0"
    SOURCE_MATCHING_VERSION_KEY: ClassVar[str] = "ontology-matching-version"
    SOURCE_MATCHING_VERSION: ClassVar[str] = "1.0.0"
    SOURCE_CHUNKS_EXTRACTION_VERSION_KEY: ClassVar[str] = (
        "chunk-extraction-version"
    )
    SOURCE_CHUNKS_EXTRACTION_VERSION: ClassVar[str] = "1.0.0"
    ENRICHMENT_VERSION_KEY: ClassVar[str] = "fuzzy-enrichment-version"
    ENRICHMENT_VERSION: ClassVar[str] = "1.0.0"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.FUZZY_CATEGORY_CANDIDATES_ENRICHED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            "fuzzy_category_candidates_enriched"
        ),
        version="1.0.0",
        name="Fuzzy Category Candidates Enriched",
        description=(
            "Fuzzy-substring enrichment of category candidates only for "
            "chunks that produced zero exact matches in the preceding "
            "stage. Score = len(shorter)/len(longer) on normalized "
            "strings that contain each other."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "suggestion",
            "file",
            "category",
            "fuzzy-match",
            "substring-match",
            "enrichment",
            "etl",
            "final",
        ],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                EtlEventContextKeys.CONTAINER_PATH: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "properties": {
                "event_path": {"type": "string"},
                "enriched_chunk_count": {"type": "integer"},
                "total_candidate_count": {"type": "integer"},
            },
        },
        log_message={
            "info": {
                "en": "Fuzzy-substring category enrichment was performed on chunks without exact matches.",
            },
            "debug_entry": {
                "en": "Running fuzzy substring enrichment over chunks that had zero exact matches.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return "Fuzzy Category Candidates Enriched"
        if normalized_language == "pt-br":
            return "Candidatos Fuzzy de Categoria Enriquecidos"
        raise ValueError(f"Unsupported presentation language: '{lang}'.")

    def description(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return (
                "Fuzzy-substring category candidates were produced only "
                "for chunks that produced zero exact matches. "
                "Score = len(shorter)/len(longer) when the normalized "
                "chunk and normalized label contain each other."
            )
        if normalized_language == "pt-br":
            return (
                "Candidatos fuzzy por substring foram produzidos "
                "apenas para chunks sem match exato. "
                "Score = len(menor)/len(maior) quando o chunk "
                "normalizado e o label normalizado se contem mutuamente."
            )
        raise ValueError(f"Unsupported presentation language: '{lang}'.")

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context,
            EtlEventContextKeys.CONTAINER_PATH,
        )
        if container_path_value is None:
            return False
        container_path: Path = Path(container_path_value).expanduser().resolve()
        event_path: Path = (
            FuzzyCategoryCandidatesEnrichedCapability.event_path(
                container_path
            )
        )
        if not event_path.is_file():
            return False
        event: Dict[str, Any] = json.loads(
            event_path.read_text(encoding="utf-8")
        )
        recorded_hash: Any = event.get(EtlEventPayloadKeys.RO_CRATE_HASH)
        if not isinstance(recorded_hash, str) or not recorded_hash.strip():
            return False
        if recorded_hash != ContainerRoCrate.file_hash(container_path):
            return False
        enrichment_version: Any = event.get(self.ENRICHMENT_VERSION_KEY)
        if enrichment_version != self.ENRICHMENT_VERSION:
            return False
        exact_version: Any = event.get(self.EXACT_SCORING_VERSION_KEY)
        if exact_version != self.EXACT_SCORING_VERSION:
            return False
        candidates: Any = event.get(self.FUZZY_CANDIDATES_KEY)
        if not isinstance(candidates, dict):
            return False
        items: Any = candidates.get(self.ITEMS_KEY)
        if not isinstance(items, list):
            return False
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, EtlEventContextKeys.CONTAINER_PATH)
        ).expanduser().resolve()
        etl_parent: Path = (
            FuzzyCategoryCandidatesEnrichedCapability.event_path(
                container_path
            ).parent
        )

        exact_event_content: str = StateWorkerAdapter.get_persisted_event(
            etl_parent,
            FileMeaningSuggestionProcessState.CATEGORY_CANDIDATES_FOUND,
        )
        exact_event: Dict[str, Any] = json.loads(exact_event_content)

        match_event_content: str = StateWorkerAdapter.get_persisted_event(
            etl_parent,
            FileMeaningSuggestionProcessState.ONTOLOGY_TERMS_MATCHED,
        )
        match_event: Dict[str, Any] = json.loads(match_event_content)

        exact_scoring_version: Any = exact_event.get(
            self.EXACT_SCORING_VERSION_KEY)
        if exact_scoring_version != self.EXACT_SCORING_VERSION:
            raise ValueError(
                "FuzzyCategoryCandidatesEnrichedCapability requires "
                "exact-stage scoring version "
                f"{self.EXACT_SCORING_VERSION!r}; found "
                f"{exact_scoring_version!r}."
            )
        matching_version: Any = match_event.get(self.SOURCE_MATCHING_VERSION_KEY)
        if matching_version != self.SOURCE_MATCHING_VERSION:
            raise ValueError(
                "FuzzyCategoryCandidatesEnrichedCapability requires "
                f"ontology matching version "
 f"{self.SOURCE_MATCHING_VERSION!r}; found "
                f"{matching_version!r}."
            )
        exact_candidates_raw: Any = exact_event.get(self.EXACT_CANDIDATES_KEY)
        if not isinstance(exact_candidates_raw, dict):
            raise ValueError(
                "FuzzyCategoryCandidatesEnrichedCapability requires "
                "'category_candidates' dict from upstream "
                "CATEGORY_CANDIDATES_FOUND event."
            )
        exact_items_raw: Any = exact_candidates_raw.get(self.ITEMS_KEY)
        if not isinstance(exact_items_raw, list):
            raise ValueError(
                "FuzzyCategoryCandidatesEnrichedCapability requires "
                "'category_candidates.items' to be a list."
            )
        matched_upstream_raw: Any = match_event.get("ontology_matches")
        if not isinstance(matched_upstream_raw, dict):
            raise ValueError(
                "FuzzyCategoryCandidatesEnrichedCapability requires "
                "'ontology_matches' object from ONTOLOGY_TERMS_MATCHED."
            )
        upstream_items_raw: Any = matched_upstream_raw.get(self.ITEMS_KEY)
        if not isinstance(upstream_items_raw, list):
            raise ValueError(
                "FuzzyCategoryCandidatesEnrichedCapability requires "
                "'ontology_matches.items' list from upstream event."
            )

        exact_chunk_ids: Set[str] = set()
        exact_lemmas: Set[str] = set()
        item_exact: Any
        for item_exact in exact_items_raw:
            if not isinstance(item_exact, dict):
                continue
            cid_exact: Any = item_exact.get(self.CHUNK_ID_KEY)
            topcats: Any = item_exact.get("top_categories")
            if not isinstance(topcats, list) or not topcats:
                continue
            if isinstance(cid_exact, str) and cid_exact.strip():
                exact_chunk_ids.add(cid_exact.strip())
            lem_exact: Any = item_exact.get("lemma")
            if isinstance(lem_exact, str) and lem_exact.strip():
                exact_lemmas.add(lem_exact.strip())

        adapter = OntologyConfigAdapter(UnsetProjectRootConfigDataAdapter())
        extractor = _OntologyTermExtractor(adapter)
        universe_terms: List[Dict[str, Any]] = extractor.extract_all_terms()

        enriched_items: List[Dict[str, Any]] = []
        total_candidate_count: int = 0
        item_up: Any
        for item_up in upstream_items_raw:
            if not isinstance(item_up, dict):
                continue
            lemma_raw: Any = item_up.get("lemma")
            language_raw: Any = item_up.get("language")
            chunk_id_raw: Any = item_up.get(self.CHUNK_ID_KEY)
            if not isinstance(lemma_raw, str) or not lemma_raw.strip():
                continue
            if not isinstance(language_raw, str) or not language_raw.strip():
                continue
            lemma_clean: str = lemma_raw.strip()
            language_clean: str = language_raw.strip()
            chunk_id_stripped: Optional[str] = None
            if isinstance(chunk_id_raw, str) and chunk_id_raw.strip():
                chunk_id_stripped = chunk_id_raw.strip()
            if chunk_id_stripped and chunk_id_stripped in exact_chunk_ids:
                continue
            if lemma_clean in exact_lemmas:
                continue
            fuzzy_cats: List[Dict[str, Any]]
            found_any: int
            fuzzy_cats, found_any = _FuzzySubstringScorer.enrich_chunk(
                lemma=lemma_clean,
                language=language_clean,
                chunk_id=chunk_id_stripped,
                ontology_terms=universe_terms,
            )
            if not fuzzy_cats:
                continue
            total_candidate_count += found_any
            enriched_items.append(
                {
                    self.CHUNK_ID_KEY: chunk_id_stripped,
                    "lemma": lemma_clean,
                    "language": language_clean,
                    "top_categories": fuzzy_cats,
                }
            )
        enriched_items.sort(
            key=lambda item: (
                -len(item["top_categories"]),
                str(item.get("language", "")),
                str(item.get("lemma", "")),
            )
        )
        matching_version_value: Any = match_event.get(
            self.SOURCE_MATCHING_VERSION_KEY)
        if not isinstance(matching_version_value, str):
            matching_version_value = ""
        exact_scoring_version_value: Any = exact_event.get(
            self.EXACT_SCORING_VERSION_KEY
        )
        if not isinstance(exact_scoring_version_value, str):
            exact_scoring_version_value = ""
        event: Dict[str, Any] = {
            "state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            EtlEventPayloadKeys.RO_CRATE_HASH: ContainerRoCrate.file_hash(container_path),
            self.SOURCE_MATCHING_VERSION_KEY: matching_version_value,
            self.EXACT_SCORING_VERSION_KEY: exact_scoring_version_value,
            self.ENRICHMENT_VERSION_KEY: self.ENRICHMENT_VERSION,
            self.FUZZY_CANDIDATES_KEY: {
                "configuration": _FuzzySubstringScorer.configuration(),
                self.ITEMS_KEY: enriched_items,
            },
            "enriched_chunk_count": len(enriched_items),
            "total_candidate_count": total_candidate_count,
        }
        event_path: Path = self._write_event(container_path, event)
        return {
            "resulting_state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            "event_path": str(event_path),
            "enriched_chunk_count": len(enriched_items),
            "total_candidate_count": total_candidate_count,
        }

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / ETL_MODULE_NAME
            / ETL_PHASE_NAME
            / ETL_ENTITY_NAME
            / cls.ETL_EVENT_FILE_NAME
        )

    @classmethod
    def _write_event(cls, container_path: Path, event: Dict[str, Any]) -> Path:
        event_path: Path = cls.event_path(container_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        serialized: str = json.dumps(
            event,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary_path: Path = event_path.with_name(f".{event_path.name}.tmp")
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(event_path)
        return event_path
