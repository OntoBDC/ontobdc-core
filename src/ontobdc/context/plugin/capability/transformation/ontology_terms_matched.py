import json
import unicodedata
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from rdflib import Graph
from rdflib.namespace import Namespace

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
from ontobdc.shared.adapter.ontology import (
    OntologyConfigAdapter,
    OntologyResourceLocator,
)
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate import ContainerRoCrate

ETL_MODULE_NAME: str = "context"
ETL_PHASE_NAME: str = "suggestion"
ETL_ENTITY_NAME: str = "file"


class _LabelNormalizer:
    """Deterministic label/chunk normalizer used for ontology term matching.

    Normalization rules (identical to the upstream path normalization stage so
    matching stays consistent across the whole suggestion pipeline):

    * strip surrounding whitespace;
    * lowercase (casefold);
    * decomposed then stripped combining marks (ASCII-folds accentuated chars);
    * collapse any internal whitespace run to one single space.
    """

    @staticmethod
    def normalize(value: str) -> str:
        stripped: str = value.strip()
        if not stripped:
            raise ValueError("LabelNormalizer requires a non-empty string.")
        casefolded: str = stripped.casefold()
        decomposed: str = unicodedata.normalize("NFKD", casefolded)
        no_marks: str = "".join(
            ch for ch in decomposed if not unicodedata.combining(ch)
        )
        collapsed: str = " ".join(no_marks.split())
        return collapsed


class _OntologyTermExtractor:
    """Extracts labelled RDF entities from every configured ontology prefix.

    Responsibility is deliberately narrow: load the central ontology adapter,
    iterate the declared prefix + type combinations, parse each graph, collect
    owl:Class / rdf:Property / skos:Concept subjects, and return a flat list
    of term records with their labels. No matching, no scoring, no chunk logic
    lives here (SRP / low coupling with the downstream matcher).
    """

    _ONTOLOGY_PREFIXES: ClassVar[Tuple[str, ...]] = tuple(
        sorted(
            set(
                list(OntologyResourceLocator._PREFIX_TO_RESOURCE_PARTS.keys())
                + [
                    # Ontologias registradas no Namespace central mas que
                    # nao possuem mapeamento no ResourceLocator ainda
                    # (resolvidas por configuracao do usuario ou cache
                    # workspace). Mantidas explicitamente para cobertura
                    # historica enquanto o mapa central e expandido.
                    "ibim",
                    "ibim_view",
                    "ibim_presentation",
                    "ibim_tile",
                    "obdc_tile",
                    "obdc_file",
                    # Prefixos externos W3C / industria. Nao possuem arquivo
                    # local no brasidatacenter; sao carregados apenas se
                    # houver override via ConfigDataAdapter. _try_load_graph
                    # retorna None para prefixos nao encontrados, sem crash.
                    "ifco",
                    "ct",
                    "dcat",
                    "schema",
                    "prov",
                ]
            )
        )
    )

    _ONTOLOGY_TYPES: ClassVar[Tuple[str, ...]] = (
        "ns",
        "view",
        "code",
        "file",
        "tbox",
        "abox",
        "default_surface_layout",
        "type",
    )

    _TERM_TYPES: ClassVar[Tuple[Tuple[str, str], ...]] = (
        ("owl", "Class"),
        ("rdf", "Property"),
        ("rdf", "type"),
        ("skos", "Concept"),
    )

    _LABEL_PREDICATES: ClassVar[Tuple[Tuple[str, str], ...]] = (
        ("rdfs", "label"),
        ("skos", "prefLabel"),
        ("skos", "altLabel"),
    )

    def __init__(self, ontology_adapter: OntologyConfigAdapter) -> None:
        self._ontology_adapter: OntologyConfigAdapter = ontology_adapter

    def extract_all_terms(self) -> List[Dict[str, Any]]:
        terms: List[Dict[str, Any]] = []
        seen_iris: set[str] = set()

        prefix: str
        for prefix in self._ONTOLOGY_PREFIXES:
            type_name: str
            for type_name in self._ONTOLOGY_TYPES:
                graph: Optional[Graph] = self._try_load_graph(prefix, type_name)
                if graph is None:
                    continue
                extracted: List[Dict[str, Any]]
                extracted = self._extract_terms_from_graph(
                    graph=graph,
                    ontology_prefix=prefix,
                    ontology_type=type_name,
                )
                term: Dict[str, Any]
                for term in extracted:
                    iri: Any = term.get("iri")
                    if not isinstance(iri, str) or not iri.strip():
                        continue
                    if iri in seen_iris:
                        continue
                    seen_iris.add(iri)
                    terms.append(term)
        return terms

    # ---------------------------------------------------------------- helpers

    def _try_load_graph(
        self, prefix: str, type_name: str
    ) -> Optional[Graph]:
        try:
            return self._ontology_adapter.get_ontology_content(
                prefix=prefix,
                type=type_name,
            )
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _extract_terms_from_graph(
        self,
        *,
        graph: Graph,
        ontology_prefix: str,
        ontology_type: str,
    ) -> List[Dict[str, Any]]:
        terms: List[Dict[str, Any]] = []
        predicate_ns_map: Dict[str, Namespace] = {}

        predicate_package: Tuple[str, str]
        for predicate_package in self._TERM_TYPES + self._LABEL_PREDICATES:
            prefix_key: str = predicate_package[0]
            namespace: Optional[Namespace]
            namespace = self._ontology_adapter.get_ontology_namespace_by_prefix(
                prefix_key
            )
            if namespace is not None:
                predicate_ns_map[prefix_key] = namespace

        owl_ns: Optional[Namespace] = predicate_ns_map.get("owl")
        rdf_ns: Optional[Namespace] = predicate_ns_map.get("rdf")
        skos_ns: Optional[Namespace] = predicate_ns_map.get("skos")
        rdfs_ns: Optional[Namespace] = predicate_ns_map.get("rdfs")

        subjects_by_type: Dict[str, Any] = {}
        if owl_ns is not None:
            subjects_by_type["http://www.w3.org/2002/07/owl#Class"] = set(
                graph.subjects(rdf_ns["type"], owl_ns["Class"]) if rdf_ns else ()
            )
        if rdf_ns is not None:
            property_set = subjects_by_type.setdefault(
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property", set()
            )
            for subject in graph.subjects(
                rdf_ns["type"], rdf_ns["Property"]
            ):
                property_set.add(subject)
        if skos_ns is not None and rdf_ns is not None:
            concept_set = subjects_by_type.setdefault(
                "http://www.w3.org/2004/02/skos/core#Concept", set()
            )
            for subject in graph.subjects(
                rdf_ns["type"], skos_ns["Concept"]
            ):
                concept_set.add(subject)

        label_predicates: List[Any] = []
        if rdfs_ns is not None:
            label_predicates.append(rdfs_ns["label"])
        if skos_ns is not None:
            label_predicates.append(skos_ns["prefLabel"])
            label_predicates.append(skos_ns["altLabel"])

        if not subjects_by_type or not label_predicates:
            return terms

        type_entries: Tuple[Tuple[str, str], ...] = (
            (
                "http://www.w3.org/2002/07/owl#Class",
                "owl:Class",
            ),
            (
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property",
                "rdf:Property",
            ),
            (
                "http://www.w3.org/2004/02/skos/core#Concept",
                "skos:Concept",
            ),
        )

        type_key: str
        type_label: str
        for type_key, type_label in type_entries:
            subjects: Any = subjects_by_type.get(type_key, set())
            for subject in subjects:
                iri_str: str = str(subject)
                if not iri_str.strip():
                    continue
                labels: Dict[str, List[str]] = {}
                predicate: Any
                for predicate in label_predicates:
                    for label_value in graph.objects(subject, predicate):
                        literal_text: str = ""
                        literal_lang: str = "en"
                        if hasattr(label_value, "value"):
                            literal_text = str(label_value.value)
                            if hasattr(label_value, "language"):
                                lang_attr: Any = getattr(label_value, "language")
                                if lang_attr:
                                    literal_lang = str(lang_attr)
                        else:
                            literal_text = str(label_value)
                        if not literal_text.strip():
                            continue
                        normalized_lang: str = (
                            literal_lang.strip().lower().replace("_", "-")
                        )
                        labels.setdefault(normalized_lang, []).append(literal_text)
                if not labels:
                    continue
                terms.append(
                    {
                        "iri": iri_str,
                        "labels": labels,
                        "ontology_prefix": ontology_prefix,
                        "ontology_type": ontology_type,
                        "term_type": type_label,
                    }
                )
        return terms


class _OntologyTermsMatcher:
    """Deterministic ontology matcher for the suggestion pipeline.

    The matcher is intentionally pre-LLM / pre-embedding. Matching is purely
    string-based so every result is explainable from corpus evidence only.

    **Single match rule (enforced):** the chunk's normalized lemma must be
    **exactly equal** to the term's normalized ``skos:prefLabel``,
    ``skos:altLabel`` or ``rdfs:label`` in one of the accepted languages.
    No bag-of-words / token-set comparisons and no substring containment
    are accepted — every match requires identity between the two normalized
    strings.
    """

    def __init__(self, ontology_terms: List[Dict[str, Any]]) -> None:
        self._normalized_terms: List[Dict[str, Any]] = []
        self._index_terms(ontology_terms)

    def match_chunk(
        self,
        *,
        lemma: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(lemma, str) or not lemma.strip():
            raise ValueError("OntologyTermsMatcher requires a non-empty lemma.")
        if not isinstance(language, str) or not language.strip():
            raise ValueError(
                "OntologyTermsMatcher requires a non-empty language code."
            )
        normalized_lemma: str = _LabelNormalizer.normalize(lemma)
        language_key: str = language.strip().lower().replace("_", "-")
        fallback_languages: Tuple[str, ...]
        if language_key.startswith("pt"):
            fallback_languages = ("pt-br", "pt", "en")
        else:
            fallback_languages = ("en", "pt-br", "pt")
        results: List[Dict[str, Any]] = []
        seen_iris: set[str] = set()
        term: Dict[str, Any]
        for term in self._normalized_terms:
            all_labels: Dict[str, List[str]] = term["labels"]
            applicable_labels: List[Tuple[str, str]] = []
            lang: str
            for lang in fallback_languages:
                bucket: Optional[List[str]] = all_labels.get(lang)
                if bucket is None:
                    continue
                label_text: str
                for label_text in bucket:
                    applicable_labels.append((lang, label_text))
            any_bucket: Optional[List[str]] = all_labels.get("")
            if any_bucket:
                for label_text in any_bucket:
                    applicable_labels.append(("", label_text))
            if not applicable_labels:
                continue
            iri: Any = term["iri"]
            if not isinstance(iri, str) or iri in seen_iris:
                continue
            chosen: Optional[Dict[str, Any]] = None
            label_lang: str
            label_text: str
            for label_lang, label_text in applicable_labels:
                match_candidate: Dict[str, Any]
                match_candidate = self._try_match_label(
                    normalized_lemma=normalized_lemma,
                    label_text=label_text,
                    term=term,
                    label_language=label_lang,
                )
                if match_candidate is None:
                    continue
                chosen = match_candidate
                break
            if chosen is not None:
                seen_iris.add(iri)
                results.append(chosen)
        results.sort(
            key=lambda item: (
                item.get("ontology_prefix", ""),
                item.get("iri", ""),
            )
        )
        return results

    # ---------------------------------------------------------------- helpers

    def _index_terms(self, ontology_terms: List[Dict[str, Any]]) -> None:
        raw_term: Dict[str, Any]
        for raw_term in ontology_terms:
            labels: Any = raw_term.get("labels")
            if not isinstance(labels, dict):
                continue
            normalized_labels: Dict[str, List[str]] = {}
            lang: Any
            for lang in labels:
                bucket: Any = labels.get(lang)
                if not isinstance(bucket, list):
                    continue
                normalized_bucket: List[str] = []
                item: Any
                for item in bucket:
                    if not isinstance(item, str) or not item.strip():
                        continue
                    try:
                        normalized_bucket.append(_LabelNormalizer.normalize(item))
                    except ValueError:
                        continue
                if normalized_bucket:
                    normalized_bucket_dedup: List[str] = list(
                        dict.fromkeys(normalized_bucket)
                    )
                    normalized_labels[str(lang)] = normalized_bucket_dedup
            if not normalized_labels:
                continue
            self._normalized_terms.append(
                {
                    "iri": raw_term.get("iri"),
                    "labels": normalized_labels,
                    "original_labels": labels,
                    "ontology_prefix": raw_term.get("ontology_prefix"),
                    "ontology_type": raw_term.get("ontology_type"),
                    "term_type": raw_term.get("term_type"),
                }
            )

    def _try_match_label(
        self,
        *,
        normalized_lemma: str,
        label_text: str,
        term: Dict[str, Any],
        label_language: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            normalized_label: str = _LabelNormalizer.normalize(label_text)
        except ValueError:
            return None
        if not normalized_label:
            return None
        if normalized_lemma != normalized_label:
            return None
        chosen_label_display: str = label_text
        original_labels: Any = term.get("original_labels", {})
        if isinstance(original_labels, dict):
            lookup_lang: str = (
                label_language if label_language else next(iter(original_labels))
            )
            candidates: Any = original_labels.get(lookup_lang)
            if isinstance(candidates, list) and candidates:
                chosen_label_display = str(candidates[0])
        return {
            "iri": term["iri"],
            "label": chosen_label_display,
            "label_language": label_language,
            "ontology_prefix": term.get("ontology_prefix"),
            "ontology_type": term.get("ontology_type"),
            "term_type": term.get("term_type"),
            "match_type": "exact",
        }


class OntologyTermsMatchedCapability(TransactionCapability):
    """Matches accepted chunks against ontology terms declared in the central
    ontology adapter (REGRA 15) and persists the deterministic result as an
    ETL event consumed by the downstream category-candidates stage.
    """

    MATCHES_KEY: ClassVar[str] = "ontology_matches"
    ITEMS_KEY: ClassVar[str] = "items"
    CHUNKS_KEY: ClassVar[str] = "chunks"
    CHUNK_ID_KEY: ClassVar[str] = "chunk_id"
    STATE_NAME: ClassVar[str] = "ontology_terms_matched"
    SOURCE_STATE_NAME: ClassVar[str] = "chunks_extracted"
    MATCHING_VERSION_KEY: ClassVar[str] = "ontology-matching-version"
    MATCHING_VERSION: ClassVar[str] = "1.0.0"
    SOURCE_EXTRACTION_VERSION_KEY: ClassVar[str] = "chunk-extraction-version"
    SOURCE_EXTRACTION_VERSION: ClassVar[str] = "1.0.0"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.ONTOLOGY_TERMS_MATCHED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            "ontology_terms_matched"
        ),
        version="1.0.0",
        name="Ontology Terms Matched",
        description=(
            "Match accepted semantic chunks against terms declared in the "
            "project ontology vocabulary and persist the deterministic "
            "string-based matches for downstream category classification."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "suggestion",
            "file",
            "ontology",
            "terms",
            "matching",
            "etl",
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
                "matched_chunk_count": {"type": "integer"},
                "total_match_count": {"type": "integer"},
                MATCHES_KEY: {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "Accepted chunks were matched against ontology terms.",
            },
            "debug_entry": {
                "en": "Matching accepted chunks against ontology vocabulary.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return "Ontology Terms Matched"
        if normalized_language == "pt-br":
            return "Termos da Ontologia Correspondidos"
        raise ValueError(f"Unsupported presentation language: '{lang}'.")

    def description(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return (
                "Accepted chunks have been compared against explicitly "
                "declared terms in the project ontology vocabulary, and the "
                "deterministic string matches were persisted for the next stage."
            )
        if normalized_language == "pt-br":
            return (
                "Os chunks aceitos foram comparados com termos explicitamente "
                "declarados no vocabulário da ontologia do projeto, e os "
                "casamentos determinísticos foram persistidos para a próxima etapa."
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
        event_path: Path = OntologyTermsMatchedCapability.event_path(container_path)
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
        matching_version: Any = event.get(self.MATCHING_VERSION_KEY)
        if matching_version != self.MATCHING_VERSION:
            return False
        source_extraction: Any = event.get(self.SOURCE_EXTRACTION_VERSION_KEY)
        if source_extraction != self.SOURCE_EXTRACTION_VERSION:
            return False
        matches: Any = event.get(self.MATCHES_KEY)
        if not isinstance(matches, dict):
            return False
        items: Any = matches.get(self.ITEMS_KEY)
        if not isinstance(items, list):
            return False
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, EtlEventContextKeys.CONTAINER_PATH)
        ).expanduser().resolve()

        chunk_event_content: str = StateWorkerAdapter.get_persisted_event(
            OntologyTermsMatchedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.CHUNKS_EXTRACTED,
        )
        chunk_event: Dict[str, Any] = json.loads(chunk_event_content)
        source_extraction: Any = chunk_event.get(self.SOURCE_EXTRACTION_VERSION_KEY)
        if source_extraction != self.SOURCE_EXTRACTION_VERSION:
            raise ValueError(
                "OntologyTermsMatchedCapability requires chunk extraction "
                f"version {self.SOURCE_EXTRACTION_VERSION!r}, found "
                f"{source_extraction!r}."
            )
        chunks_raw: Any = chunk_event.get(self.CHUNKS_KEY)
        if not isinstance(chunks_raw, dict):
            raise ValueError(
                "OntologyTermsMatchedCapability requires a 'chunks' object "
                "from the upstream chunks_extracted event."
            )
        items_raw: Any = chunks_raw.get(self.ITEMS_KEY)
        if not isinstance(items_raw, list):
            raise ValueError(
                "OntologyTermsMatchedCapability requires 'chunks.items' "
                "from the upstream chunks_extracted event to be a list."
            )
        chunk_items: List[Dict[str, Any]] = items_raw

        ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
            config_adapter=UnsetProjectRootConfigDataAdapter(),
        )
        extractor: _OntologyTermExtractor = _OntologyTermExtractor(ontology_adapter)
        ontology_terms: List[Dict[str, Any]] = extractor.extract_all_terms()
        matcher: _OntologyTermsMatcher = _OntologyTermsMatcher(ontology_terms)

        matched_items: List[Dict[str, Any]] = []
        total_match_count: int = 0
        chunk: Dict[str, Any]
        for chunk in chunk_items:
            lemma_raw: Any = chunk.get("lemma")
            language_raw: Any = chunk.get("language")
            chunk_id_raw: Any = chunk.get(self.CHUNK_ID_KEY)
            if not isinstance(lemma_raw, str) or not lemma_raw.strip():
                raise ValueError(
                    "OntologyTermsMatchedCapability requires every chunk "
                    "to carry a non-empty 'lemma'."
                )
            if not isinstance(language_raw, str) or not language_raw.strip():
                raise ValueError(
                    "OntologyTermsMatchedCapability requires every chunk "
                    "to carry a non-empty 'language'."
                )
            matches: List[Dict[str, Any]] = matcher.match_chunk(
                lemma=lemma_raw.strip(),
                language=language_raw.strip(),
            )
            total_match_count += len(matches)
            matched_items.append(
                {
                    self.CHUNK_ID_KEY: chunk_id_raw,
                    "lemma": lemma_raw.strip(),
                    "language": language_raw.strip(),
                    "matched_terms": matches,
                }
            )
        matched_items.sort(
            key=lambda item: (
                -len(item["matched_terms"]),
                str(item.get("language", "")),
                str(item.get("lemma", "")),
            )
        )
        extraction_version: Any = chunk_event.get(self.SOURCE_EXTRACTION_VERSION_KEY)
        if not isinstance(extraction_version, str):
            extraction_version = ""
        event: Dict[str, Any] = {
            "state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            EtlEventPayloadKeys.RO_CRATE_HASH: ContainerRoCrate.file_hash(container_path),
            self.SOURCE_EXTRACTION_VERSION_KEY: extraction_version,
            self.MATCHING_VERSION_KEY: self.MATCHING_VERSION,
            self.MATCHES_KEY: {
                "configuration": {
                    "matching_rule": "normalized-string-equality",
                    "matching_version": self.MATCHING_VERSION,
                    "ontology_prefix_count": len(
                        _OntologyTermExtractor._ONTOLOGY_PREFIXES
                    ),
                },
                self.ITEMS_KEY: matched_items,
            },
            "matched_chunk_count": len(matched_items),
            "total_match_count": total_match_count,
        }
        event_path: Path = self._write_event(container_path, event)
        return {
            "resulting_state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            "event_path": str(event_path),
            "matched_chunk_count": len(matched_items),
            "total_match_count": total_match_count,
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
