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


class _ChunkMatchResult:
    def __init__(
        self,
        *,
        match_type: str,
        score: float,
        category_iri: Optional[str],
        category_label: Optional[str],
        ontology_prefix: Optional[str],
        term_type: Optional[str],
        matched_term_label: Optional[str],
    ) -> None:
        self.match_type: str = match_type
        self.score: float = score
        self.category_iri: Optional[str] = category_iri
        self.category_label: Optional[str] = category_label
        self.ontology_prefix: Optional[str] = ontology_prefix
        self.term_type: Optional[str] = term_type
        self.matched_term_label: Optional[str] = matched_term_label


class _ExactFirstMatcher:
    """Run EXACT match first; if empty, fall back to FUZZY substring match.

    Matches are computed per (chunk lemma, chunk language). Exact match
    uses normalized string equality (score 1.0). Fuzzy match uses the
    user-specified length-ratio rule: min(A,B)/max(A,B) whenever one
    normalized string contains the other. If neither produces a hit the
    chunk is recorded with match_type = 'unmatched' and score 0.0.
    """

    EXACT_SCORE: ClassVar[float] = 1.0
    MIN_FUZZY_SCORE: ClassVar[float] = 0.2
    TOP_N_PER_CHUNK: ClassVar[int] = 5

    @classmethod
    def configuration(cls) -> Dict[str, Any]:
        return {
            "exact_score": cls.EXACT_SCORE,
            "min_fuzzy_score": cls.MIN_FUZZY_SCORE,
            "top_n_per_chunk": cls.TOP_N_PER_CHUNK,
            "exact_rule": "normalized_label_equality",
            "fuzzy_rule": "min(len(a),len(b))/max(len(a),len(b)) iff one normalized contains the other",
            "unmatched_rule": "no exact and no fuzzy above min_fuzzy_score",
        }

    @classmethod
    def _flatten_labels(
        cls,
        *,
        labels_raw: Any,
    ) -> List[Tuple[str, str]]:
        flat: List[Tuple[str, str]] = []
        if isinstance(labels_raw, list):
            for entry in labels_raw:
                if not isinstance(entry, dict):
                    continue
                lt: Any = entry.get("label")
                ll: Any = entry.get("language")
                if isinstance(lt, str) and lt.strip():
                    flat.append((
                        lt.strip(),
                        (ll.strip().lower().replace("_", "-")
                         if isinstance(ll, str) and ll.strip()
                         else ""),
                    ))
        elif isinstance(labels_raw, dict):
            for lang_key, label_values in labels_raw.items():
                if not isinstance(label_values, list):
                    continue
                lang_clean: str = (
                    str(lang_key).strip().lower().replace("_", "-")
                    if isinstance(lang_key, str) and lang_key.strip()
                    else ""
                )
                one_label: Any
                for one_label in label_values:
                    if isinstance(one_label, str) and one_label.strip():
                        flat.append((one_label.strip(), lang_clean))
        return flat

    @classmethod
    def _accept_language(
        cls,
        *,
        chunk_lang: str,
        label_lang: str,
    ) -> bool:
        if not label_lang:
            return True
        if chunk_lang == "pt-br":
            return label_lang in {"pt-br", "pt", "en"}
        if chunk_lang == "pt":
            return label_lang in {"pt", "pt-br", "en"}
        return label_lang == chunk_lang or label_lang == "en"

    @classmethod
    def _fuzzy_ratio(
        cls,
        *,
        a_norm: str,
        b_norm: str,
    ) -> Optional[float]:
        if not a_norm or not b_norm:
            return None
        if a_norm == b_norm:
            return cls.EXACT_SCORE
        if a_norm in b_norm or b_norm in a_norm:
            denom: int = max(len(a_norm), len(b_norm))
            if denom < 1:
                return None
            return float(min(len(a_norm), len(b_norm))) / float(denom)
        return None

    @classmethod
    def match_chunk(
        cls,
        *,
        lemma: str,
        language: str,
        ontology_terms: List[Dict[str, Any]],
        exact_matches: List[Dict[str, Any]],
    ) -> List[_ChunkMatchResult]:
        lemma_clean: str = lemma.strip()
        if not lemma_clean:
            return []
        chunk_lang_clean: str = language.strip().lower().replace("_", "-")
        lemma_norm: str = _LabelNormalizer.normalize(lemma_clean)
        if not lemma_norm:
            return []
        results: List[_ChunkMatchResult] = []
        seen_exact_iris: Set[str] = set()
        em: Dict[str, Any]
        for em in exact_matches:
            mt: Any = em.get("match_type")
            if mt != "exact":
                raise ValueError(
                    "_ExactFirstMatcher only accepts match_type='exact' "
                    f"from upstream; got {mt!r} for lemma {lemma!r}."
                )
            iri: Any = em.get("iri")
            if not isinstance(iri, str) or not iri.strip():
                raise ValueError(
                    "_ExactFirstMatcher requires every exact match to "
                    "carry a non-empty 'iri'."
                )
            seen_exact_iris.add(iri.strip())
            label_raw: Any = em.get("label")
            prefix_raw: Any = em.get("ontology_prefix")
            tt_raw: Any = em.get("term_type")
            results.append(_ChunkMatchResult(
                match_type="exact",
                score=cls.EXACT_SCORE,
                category_iri=iri.strip(),
                category_label=(
                    label_raw.strip()
                    if isinstance(label_raw, str) and label_raw.strip()
                    else iri.strip()
                ),
                ontology_prefix=(
                    prefix_raw if isinstance(prefix_raw, str) else ""
                ),
                term_type=(
                    tt_raw if isinstance(tt_raw, str) else ""
                ),
                matched_term_label=(
                    label_raw.strip()
                    if isinstance(label_raw, str) and label_raw.strip()
                    else iri.strip()
                ),
            ))
        if results:
            results.sort(
                key=lambda r: (
                    -r.score,
                    str(r.ontology_prefix or ""),
                    str(r.category_label or ""),
                )
            )
            return results[:cls.TOP_N_PER_CHUNK]
        fuzzy_candidates: List[_ChunkMatchResult] = []
        seen_fuzzy_iris: Set[str] = set()
        term: Dict[str, Any]
        for term in ontology_terms:
            iri_raw: Any = term.get("iri")
            if not isinstance(iri_raw, str) or not iri_raw.strip():
                continue
            if iri_raw.strip() in seen_fuzzy_iris:
                continue
            labels_raw: Any = term.get("labels")
            flat: List[Tuple[str, str]] = cls._flatten_labels(
                labels_raw=labels_raw,
            )
            if not flat:
                continue
            term_type_raw: Any = term.get("term_type")
            ontology_prefix_raw: Any = term.get("ontology_prefix")
            best_label_text: Optional[str] = None
            best_score: float = 0.0
            for (label_text, label_lang) in flat:
                if not cls._accept_language(
                    chunk_lang=chunk_lang_clean,
                    label_lang=label_lang,
                ):
                    continue
                label_norm: str = _LabelNormalizer.normalize(label_text)
                if not label_norm:
                    continue
                ratio: Optional[float] = cls._fuzzy_ratio(
                    a_norm=lemma_norm,
                    b_norm=label_norm,
                )
                if ratio is None:
                    continue
                if ratio < cls.MIN_FUZZY_SCORE:
                    continue
                if ratio <= best_score and best_label_text is not None:
                    continue
                best_score = ratio
                best_label_text = label_text
            if best_label_text is None:
                continue
            seen_fuzzy_iris.add(iri_raw.strip())
            fuzzy_candidates.append(_ChunkMatchResult(
                match_type="fuzzy-substring",
                score=best_score,
                category_iri=iri_raw.strip(),
                category_label=best_label_text,
                ontology_prefix=(
                    ontology_prefix_raw
                    if isinstance(ontology_prefix_raw, str)
                    else ""
                ),
                term_type=(
                    term_type_raw if isinstance(term_type_raw, str) else ""
                ),
                matched_term_label=best_label_text,
            ))
        if fuzzy_candidates:
            fuzzy_candidates.sort(
                key=lambda r: (
                    -r.score,
                    str(r.ontology_prefix or ""),
                    str(r.category_label or ""),
                )
            )
            return fuzzy_candidates[:cls.TOP_N_PER_CHUNK]
        return [
            _ChunkMatchResult(
                match_type="unmatched",
                score=0.0,
                category_iri=None,
                category_label=None,
                ontology_prefix=None,
                term_type=None,
                matched_term_label=None,
            ),
        ]


class CategoryCandidatesFoundCapability(TransactionCapability):
    """State-10 of the file-meaning suggestion pipeline.

    Produces a HIERARCHICAL output aggregated by ro-crate FILE:

    - ``files`` -> per-file entry with ro-crate @id and path
      - ``categories`` -> per-category (ontology term) bucket within the file
        - ``chunks`` -> the chunks of the file that were matched into
          the parent category, each with its own lemma, offsets in the
          path, match_type (``exact`` / ``fuzzy-substring`` /
          ``unmatched``), and score.

    Exact matches have deterministic score = 1.0 and come from the
    upstream ONTOLOGY_TERMS_MATCHED event. When a chunk has zero exact
    matches the capability runs an in-process fuzzy-substring pass over
    the central ontology term universe and falls back to match_type =
    ``unmatched`` (score 0.0) if nothing is found.

    EVERY accepted chunk is always present in the output regardless of
    whether it matched anything; unmatched chunks are placed in a
    synthetic ``__unmatched__`` category bucket inside their file.
    """

    UPSTREAM_MATCHES_KEY: ClassVar[str] = "ontology_matches"
    CHUNKS_KEY: ClassVar[str] = "chunks"
    ITEMS_KEY: ClassVar[str] = "items"
    CHUNK_ID_KEY: ClassVar[str] = "chunk_id"
    FILES_KEY: ClassVar[str] = "files"
    UNMATCHED_CATEGORY_IRI: ClassVar[str] = "__unmatched__"
    STATE_NAME: ClassVar[str] = "category_candidates_found"
    SCORING_VERSION_KEY: ClassVar[str] = "category-scoring-version"
    SCORING_VERSION: ClassVar[str] = "2.0.0"
    SOURCE_MATCHING_VERSION_KEY: ClassVar[str] = "ontology-matching-version"
    SOURCE_MATCHING_VERSION: ClassVar[str] = "1.0.0"
    SOURCE_CHUNKS_EXTRACTION_VERSION_KEY: ClassVar[str] = (
        "chunk-extraction-version"
    )
    SOURCE_CHUNKS_EXTRACTION_VERSION: ClassVar[str] = "1.0.0"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.CATEGORY_CANDIDATES_FOUND.value}.json"
    )

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            "category_candidates_found"
        ),
        version="2.0.0",
        name="Category Candidates Found",
        description=(
            "Hierarchical category candidates grouped by ro-crate file, "
            "then by ontology category, then by chunk inside each file. "
            "Exact matches score 1.0; fuzzy matches use "
            "min(len)/max(len) substring-length ratio; unmatched chunks "
            "are preserved in a synthetic bucket with score 0."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "suggestion",
            "file",
            "category",
            "files-grouping",
            "exact-match",
            "fuzzy-substring",
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
                "file_count": {"type": "integer"},
                "file_with_match_count": {"type": "integer"},
                "chunk_count": {"type": "integer"},
                "exact_chunk_count": {"type": "integer"},
                "fuzzy_chunk_count": {"type": "integer"},
                "unmatched_chunk_count": {"type": "integer"},
            },
        },
        log_message={
            "info": {
                "en": "Hierarchical category candidates per file, per category, per chunk were produced.",
            },
            "debug_entry": {
                "en": "Grouping chunks by ro-crate file and by ontology category, with exact/fuzzy/unmatched scoring.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return "Category Candidates Found"
        if normalized_language == "pt-br":
            return "Candidatos de Categoria Encontrados"
        raise ValueError(f"Unsupported presentation language: '{lang}'.")

    def description(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return (
                "Hierarchical category candidates aggregated per ro-crate "
                "file, then per ontology category, with every accepted "
                "chunk recorded inside its file's category buckets."
            )
        if normalized_language == "pt-br":
            return (
                "Candidatos de categoria hierarquicos agregados por "
                "arquivo do ro-crate, depois por categoria da ontologia, "
                "com todo chunk aceito registrado nos buckets de seu "
                "arquivo."
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
        event_path: Path = CategoryCandidatesFoundCapability.event_path(
            container_path
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
        scoring_version: Any = event.get(self.SCORING_VERSION_KEY)
        if scoring_version != self.SCORING_VERSION:
            return False
        matching_version: Any = event.get(self.SOURCE_MATCHING_VERSION_KEY)
        if matching_version != self.SOURCE_MATCHING_VERSION:
            return False
        files_payload: Any = event.get(self.FILES_KEY)
        if not isinstance(files_payload, list):
            return False
        return True

    @staticmethod
    def _ro_crate_files(container_path: Path) -> List[Dict[str, Any]]:
        manifest_path: Path = container_path / "ro-crate-metadata.json"
        if not manifest_path.is_file():
            return []
        try:
            manifest: Dict[str, Any] = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except Exception:
            return []
        graph_raw: Any = manifest.get("@graph")
        if not isinstance(graph_raw, list):
            return []
        entries: List[Dict[str, Any]] = []
        entry: Any
        for entry in graph_raw:
            if not isinstance(entry, dict):
                continue
            raw_type: Any = entry.get("@type")
            types: Set[str] = set()
            if isinstance(raw_type, str) and raw_type.strip():
                types.add(raw_type.strip())
            elif isinstance(raw_type, list):
                for t in raw_type:
                    if isinstance(t, str) and t.strip():
                        types.add(t.strip())
            if "File" not in types:
                continue
            entry_id_raw: Any = entry.get("@id")
            if not isinstance(entry_id_raw, str) or not entry_id_raw.strip():
                continue
            if entry_id_raw.startswith("ro-crate-metadata"):
                continue
            entries.append(
                {
                    "file_id": entry_id_raw.strip(),
                    "file_path": entry_id_raw.strip(),
                    "name": (
                        entry["name"].strip()
                        if isinstance(entry.get("name"), str)
                        and entry.get("name").strip()
                        else entry_id_raw.strip()
                    ),
                }
            )
        entries.sort(key=lambda e: (str(e["file_path"]), str(e["file_id"])))
        return entries

    @classmethod
    def _str(cls, value: Any, *, default: str = "") -> str:
        if isinstance(value, str):
            return value
        return default

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, EtlEventContextKeys.CONTAINER_PATH)
        ).expanduser().resolve()
        etl_parent: Path = CategoryCandidatesFoundCapability.event_path(
            container_path
        ).parent

        match_event_content: str = StateWorkerAdapter.get_persisted_event(
            etl_parent,
            FileMeaningSuggestionProcessState.ONTOLOGY_TERMS_MATCHED,
        )
        match_event: Dict[str, Any] = json.loads(match_event_content)

        chunks_event_content: str = StateWorkerAdapter.get_persisted_event(
            etl_parent,
            FileMeaningSuggestionProcessState.CHUNKS_EXTRACTED,
        )
        chunks_event: Dict[str, Any] = json.loads(chunks_event_content)

        matching_version: Any = match_event.get(self.SOURCE_MATCHING_VERSION_KEY)
        if matching_version != self.SOURCE_MATCHING_VERSION:
            raise ValueError(
                "CategoryCandidatesFoundCapability requires "
                f"ontology matching version "
                f"{self.SOURCE_MATCHING_VERSION!r}; found "
                f"{matching_version!r}."
            )
        extraction_version: Any = chunks_event.get(
            self.SOURCE_CHUNKS_EXTRACTION_VERSION_KEY
        )
        if extraction_version != self.SOURCE_CHUNKS_EXTRACTION_VERSION:
            raise ValueError(
                "CategoryCandidatesFoundCapability requires "
                f"chunks extraction version "
                f"{self.SOURCE_CHUNKS_EXTRACTION_VERSION!r}; found "
                f"{extraction_version!r}."
            )
        matches_raw: Any = match_event.get(self.UPSTREAM_MATCHES_KEY)
        if not isinstance(matches_raw, dict):
            raise ValueError(
                "CategoryCandidatesFoundCapability requires "
                "'ontology_matches' dict from ONTOLOGY_TERMS_MATCHED."
            )
        match_items_raw: Any = matches_raw.get(self.ITEMS_KEY)
        if not isinstance(match_items_raw, list):
            raise ValueError(
                "CategoryCandidatesFoundCapability requires "
                "'ontology_matches.items' list."
            )
        chunks_raw: Any = chunks_event.get(self.CHUNKS_KEY)
        if not isinstance(chunks_raw, dict):
            raise ValueError(
                "CategoryCandidatesFoundCapability requires "
                "'chunks' dict from CHUNKS_EXTRACTED."
            )
        chunk_items_raw: Any = chunks_raw.get(self.ITEMS_KEY)
        if not isinstance(chunk_items_raw, list):
            raise ValueError(
                "CategoryCandidatesFoundCapability requires "
                "'chunks.items' list from CHUNKS_EXTRACTED."
            )
        exact_by_chunk_id: Dict[str, List[Dict[str, Any]]] = {}
        exact_by_lemma_lang: Dict[str, List[Dict[str, Any]]] = {}
        mi: Any
        for mi in match_items_raw:
            if not isinstance(mi, dict):
                continue
            cid_raw: Any = mi.get(self.CHUNK_ID_KEY)
            lemma_raw: Any = mi.get("lemma")
            lang_raw: Any = mi.get("language")
            mt_list: Any = mi.get("matched_terms")
            if not isinstance(mt_list, list):
                continue
            if not mt_list:
                continue
            if (
                isinstance(cid_raw, str)
                and cid_raw.strip()
            ):
                exact_by_chunk_id[cid_raw.strip()] = mt_list
            if (
                isinstance(lemma_raw, str)
                and lemma_raw.strip()
                and isinstance(lang_raw, str)
                and lang_raw.strip()
            ):
                key: str = (
                    lemma_raw.strip()
                    + "||"
                    + lang_raw.strip().lower().replace("_", "-")
                )
                exact_by_lemma_lang[key] = mt_list

        adapter = OntologyConfigAdapter(UnsetProjectRootConfigDataAdapter())
        extractor = _OntologyTermExtractor(adapter)
        universe_terms: List[Dict[str, Any]] = extractor.extract_all_terms()

        ro_files: List[Dict[str, Any]] = (
            CategoryCandidatesFoundCapability._ro_crate_files(container_path)
        )
        ro_files_by_path: Dict[str, Dict[str, Any]] = {}
        rf: Dict[str, Any]
        for rf in ro_files:
            ro_files_by_path[str(rf["file_path"])] = rf

        unmatched_bucket_key: Tuple[str, str, str, str] = (
            self.UNMATCHED_CATEGORY_IRI,
            "Unmatched",
            "",
            "",
        )

        file_to_cat_to_chunks: Dict[
            str,
            Dict[Tuple[str, str, str, str], List[Dict[str, Any]]],
        ] = {}
        file_meta: Dict[str, Dict[str, Any]] = {}
        chunk_total: int = 0
        exact_chunk_count: int = 0
        fuzzy_chunk_count: int = 0
        unmatched_chunk_count: int = 0
        ci: Any
        for ci in chunk_items_raw:
            if not isinstance(ci, dict):
                continue
            cid_value_raw: Any = ci.get(self.CHUNK_ID_KEY)
            lemma_value_raw: Any = ci.get("lemma")
            lang_value_raw: Any = ci.get("language")
            occs_raw: Any = ci.get("occurrences")
            if (
                not isinstance(lemma_value_raw, str)
                or not lemma_value_raw.strip()
            ):
                continue
            if (
                not isinstance(lang_value_raw, str)
                or not lang_value_raw.strip()
            ):
                continue
            chunk_id_value: str
            if isinstance(cid_value_raw, str) and cid_value_raw.strip():
                chunk_id_value = cid_value_raw.strip()
            else:
                chunk_id_value = ""
            lemma_clean_value: str = lemma_value_raw.strip()
            lang_clean_value: str = lang_value_raw.strip()
            exact_list: List[Dict[str, Any]]
            lookup_key: str = (
                lemma_clean_value
                + "||"
                + lang_clean_value.lower().replace("_", "-")
            )
            if chunk_id_value and chunk_id_value in exact_by_chunk_id:
                exact_list = exact_by_chunk_id[chunk_id_value]
            elif lookup_key in exact_by_lemma_lang:
                exact_list = exact_by_lemma_lang[lookup_key]
            else:
                exact_list = []
            matches: List[_ChunkMatchResult] = (
                _ExactFirstMatcher.match_chunk(
                    lemma=lemma_clean_value,
                    language=lang_clean_value,
                    ontology_terms=universe_terms,
                    exact_matches=exact_list,
                )
            )
            has_exact: bool = any(
                m.match_type == "exact" for m in matches
            )
            has_fuzzy: bool = any(
                m.match_type == "fuzzy-substring" for m in matches
            )
            chunk_total += 1
            if has_exact:
                exact_chunk_count += 1
            elif has_fuzzy:
                fuzzy_chunk_count += 1
            else:
                unmatched_chunk_count += 1
            if not isinstance(occs_raw, list) or not occs_raw:
                continue
            occ: Any
            for occ in occs_raw:
                if not isinstance(occ, dict):
                    continue
                sp_raw: Any = occ.get("source_path")
                sid_raw: Any = occ.get("source_id")
                file_path_key: Optional[str] = None
                if isinstance(sp_raw, str) and sp_raw.strip():
                    file_path_key = sp_raw.strip()
                elif isinstance(sid_raw, str) and sid_raw.strip():
                    file_path_key = sid_raw.strip()
                if file_path_key is None:
                    continue
                if file_path_key not in file_meta:
                    if file_path_key in ro_files_by_path:
                        file_meta[file_path_key] = {
                            "file_id": ro_files_by_path[file_path_key][
                                "file_id"
                            ],
                            "file_path": file_path_key,
                            "file_name": ro_files_by_path[file_path_key][
                                "name"
                            ],
                        }
                    else:
                        file_meta[file_path_key] = {
                            "file_id": file_path_key,
                            "file_path": file_path_key,
                            "file_name": file_path_key,
                        }
                    file_to_cat_to_chunks[file_path_key] = {}
                buckets: Dict[
                    Tuple[str, str, str, str],
                    List[Dict[str, Any]],
                ] = file_to_cat_to_chunks[file_path_key]
                start_raw: Any = occ.get("start")
                end_raw: Any = occ.get("end")
                start_value: int = (
                    int(start_raw) if isinstance(start_raw, int) else 0
                )
                end_value: int = (
                    int(end_raw) if isinstance(end_raw, int) else start_value
                )
                matched: _ChunkMatchResult
                for matched in matches:
                    if matched.category_iri is not None:
                        bucket: Tuple[str, str, str, str] = (
                            matched.category_iri,
                            matched.category_label or "",
                            matched.ontology_prefix or "",
                            matched.term_type or "",
                        )
                    else:
                        bucket = unmatched_bucket_key
                    entry_data: Dict[str, Any] = {
                        self.CHUNK_ID_KEY: chunk_id_value,
                        "lemma": lemma_clean_value,
                        "language": lang_clean_value,
                        "start": start_value,
                        "end": end_value,
                        "match_type": matched.match_type,
                        "score": matched.score,
                    }
                    if matched.matched_term_label is not None:
                        entry_data["matched_term_label"] = (
                            matched.matched_term_label
                        )
                    if bucket not in buckets:
                        buckets[bucket] = []
                    buckets[bucket].append(entry_data)
        files_output: List[Dict[str, Any]] = []
        for fpath in sorted(file_meta.keys()):
            entry_file: Dict[str, Any] = {
                "file_id": file_meta[fpath]["file_id"],
                "file_path": file_meta[fpath]["file_path"],
                "file_name": file_meta[fpath]["file_name"],
                "categories": [],
            }
            buckets_for_file = file_to_cat_to_chunks[fpath]
            category_entries: List[Dict[str, Any]] = []
            for bucket_key in sorted(
                buckets_for_file.keys(),
                key=lambda bk: (
                    1 if bk[0] == self.UNMATCHED_CATEGORY_IRI else 0,
                    str(bk[2]),
                    str(bk[1]),
                    str(bk[0]),
                ),
            ):
                (
                    c_iri,
                    c_label,
                    c_prefix,
                    c_ttype,
                ) = bucket_key
                chunk_list: List[Dict[str, Any]] = buckets_for_file[bucket_key]
                chunk_list.sort(
                    key=lambda c: (
                        int(c.get("start", 0) or 0),
                        str(c.get("lemma", "")),
                        str(c.get(self.CHUNK_ID_KEY, "")),
                    )
                )
                if bucket_key == unmatched_bucket_key:
                    cat_entry: Dict[str, Any] = {
                        "category_iri": self.UNMATCHED_CATEGORY_IRI,
                        "category_label": "Unmatched chunks",
                        "ontology_prefix": "",
                        "term_type": "",
                        "chunks": chunk_list,
                    }
                else:
                    cat_entry = {
                        "category_iri": c_iri,
                        "category_label": c_label,
                        "ontology_prefix": c_prefix,
                        "term_type": c_ttype,
                        "chunks": chunk_list,
                    }
                category_entries.append(cat_entry)
            entry_file["categories"] = category_entries
            files_output.append(entry_file)
        matching_version_value: Any = match_event.get(
            self.SOURCE_MATCHING_VERSION_KEY
        )
        if not isinstance(matching_version_value, str):
            matching_version_value = ""
        extraction_version_value: Any = chunks_event.get(
            self.SOURCE_CHUNKS_EXTRACTION_VERSION_KEY
        )
        if not isinstance(extraction_version_value, str):
            extraction_version_value = ""
        files_with_match_count: int = sum(
            1 for f in files_output if any(
                c.get("category_iri") != self.UNMATCHED_CATEGORY_IRI
                for c in (f.get("categories") or [])
            )
        )
        event: Dict[str, Any] = {
            "state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            EtlEventPayloadKeys.RO_CRATE_HASH: ContainerRoCrate.file_hash(container_path),
            self.SOURCE_MATCHING_VERSION_KEY: matching_version_value,
            self.SOURCE_CHUNKS_EXTRACTION_VERSION_KEY: (
                extraction_version_value
            ),
            self.SCORING_VERSION_KEY: self.SCORING_VERSION,
            "matcher_configuration": _ExactFirstMatcher.configuration(),
            self.FILES_KEY: files_output,
            "file_count": len(files_output),
            "file_with_match_count": files_with_match_count,
            "chunk_count": chunk_total,
            "exact_chunk_count": exact_chunk_count,
            "fuzzy_chunk_count": fuzzy_chunk_count,
            "unmatched_chunk_count": unmatched_chunk_count,
        }
        event_path: Path = self._write_event(container_path, event)
        return {
            "resulting_state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            "event_path": str(event_path),
            "file_count": len(files_output),
            "file_with_match_count": files_with_match_count,
            "chunk_count": chunk_total,
            "exact_chunk_count": exact_chunk_count,
            "fuzzy_chunk_count": fuzzy_chunk_count,
            "unmatched_chunk_count": unmatched_chunk_count,
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
            sort_keys=False,
        )
        temporary_path: Path = event_path.with_name(f".{event_path.name}.tmp")
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(event_path)
        return event_path
