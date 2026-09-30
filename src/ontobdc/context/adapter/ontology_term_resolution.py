import unicodedata
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from rdflib import Graph
from rdflib.term import Node, URIRef, Literal
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import (
    OntologyConfigAdapter,
    OntologyResourceLocator,
)


class OntologyDictionaryTermExtractor:
    """Extract labelled RDF terms from the configured ontology universe."""

    ONTOLOGY_PREFIXES: ClassVar[Tuple[str, ...]] = tuple(
        sorted(
            set(
                list(OntologyResourceLocator._PREFIX_TO_RESOURCE_PARTS.keys())
                + [
                    "ibim",
                    "ibim_view",
                    "ibim_presentation",
                    "ibim_tile",
                    "obdc_tile",
                    "obdc_file",
                    "ifco",
                    "ct",
                    "dcat",
                    "schema",
                    "prov",
                ]
            )
        )
    )
    ONTOLOGY_TYPES: ClassVar[Tuple[str, ...]] = (
        "ns",
        "view",
        "code",
        "file",
        "tbox",
        "abox",
        "default_surface_layout",
        "type",
        "kind",
    )
    TERM_TYPES: ClassVar[Tuple[Tuple[str, Node], ...]] = (
        ("owl:Class", OWL.Class),
        ("rdf:Property", RDF.Property),
        ("skos:Concept", SKOS.Concept),
    )
    LABEL_PREDICATES: ClassVar[Tuple[Node, ...]] = (
        RDFS.label,
        SKOS.prefLabel,
        SKOS.altLabel,
    )
    UNTAGGED_LANGUAGE: ClassVar[str] = ""

    def __init__(self, ontology_adapter: OntologyConfigAdapter) -> None:
        self._ontology_adapter: OntologyConfigAdapter = ontology_adapter

    def extract_all_terms(self) -> List[Dict[str, Any]]:
        """
        Return every labelled term, once per IRI.

        Each prefix is probed for each known ontology file type; a missing
        combination is part of the probe and is skipped, while any other
        failure to read an existing ontology propagates.
        """
        terms: List[Dict[str, Any]] = []
        seen_iris: Set[str] = set()
        prefix: str
        for prefix in self.ONTOLOGY_PREFIXES:
            type_name: str
            for type_name in self.ONTOLOGY_TYPES:
                graph: Optional[Graph] = self._load_graph(prefix, type_name)
                if graph is None:
                    continue
                term: Dict[str, Any]
                for term in self._extract_terms_from_graph(
                    graph=graph,
                    ontology_prefix=prefix,
                    ontology_type=type_name,
                ):
                    if term["iri"] in seen_iris:
                        continue
                    seen_iris.add(term["iri"])
                    terms.append(term)
        return terms

    def _load_graph(self, prefix: str, type_name: str) -> Optional[Graph]:
        try:
            return self._ontology_adapter.get_ontology_content(
                prefix=prefix,
                type=type_name,
            )
        except FileNotFoundError:
            return None

    def _extract_terms_from_graph(
        self,
        *,
        graph: Graph,
        ontology_prefix: str,
        ontology_type: str,
    ) -> List[Dict[str, Any]]:
        terms: List[Dict[str, Any]] = []
        term_type: str
        type_node: Node
        for term_type, type_node in self.TERM_TYPES:
            subject: Node
            for subject in sorted(set(graph.subjects(RDF.type, type_node))):
                if not isinstance(subject, URIRef):
                    continue
                labels: Dict[str, List[str]] = self._labels_of(graph, subject)
                if not labels:
                    continue
                terms.append(
                    {
                        "iri": str(subject),
                        "labels": labels,
                        "ontology_prefix": ontology_prefix,
                        "ontology_type": ontology_type,
                        "term_type": term_type,
                    }
                )
        return terms

    def _labels_of(self, graph: Graph, subject: Node) -> Dict[str, List[str]]:
        labels: Dict[str, List[str]] = {}
        predicate: Node
        for predicate in self.LABEL_PREDICATES:
            label_value: Node
            for label_value in graph.objects(subject, predicate):
                if not isinstance(label_value, Literal):
                    continue
                label_text: str = str(label_value).strip()
                if not label_text:
                    continue
                language: str = (
                    label_value.language.strip().lower().replace("_", "-")
                    if label_value.language
                    else self.UNTAGGED_LANGUAGE
                )
                bucket: List[str] = labels.setdefault(language, [])
                if label_text not in bucket:
                    bucket.append(label_text)
        return labels


class OntologyTermResolver:
    """
    Resolve a lemma against the ontology dictionary.

    The result follows one of two deliberately different contracts: exact
    matches when at least one label equals the lemma, otherwise scored
    fuzzy-substring candidates. Finding neither is an error.
    """

    EXACT_MATCH_TYPE: ClassVar[str] = "exact"
    CANDIDATE_MATCH_TYPE: ClassVar[str] = "fuzzy-substring"
    MIN_FUZZY_SCORE: ClassVar[float] = 0.2
    TOP_N: ClassVar[int] = 5

    def __init__(self, extractor: OntologyDictionaryTermExtractor) -> None:
        self._extractor: OntologyDictionaryTermExtractor = extractor

    @classmethod
    def from_configuration(cls) -> "OntologyTermResolver":
        return cls(
            OntologyDictionaryTermExtractor(
                OntologyConfigAdapter(UnsetProjectRootConfigDataAdapter())
            )
        )

    def resolve(self, *, lemma: str, language: str) -> Dict[str, Any]:
        terms: List[Dict[str, Any]] = self._extractor.extract_all_terms()
        normalized_lemma: str = self._normalize(lemma)
        if not normalized_lemma:
            raise ValueError("Ontology term resolution requires a non-empty lemma.")

        exact_matches: List[Dict[str, Any]] = self._exact_matches(
            terms=terms,
            normalized_lemma=normalized_lemma,
            language=language,
        )
        if exact_matches:
            return {
                "match_type": self.EXACT_MATCH_TYPE,
                "exact_matches": exact_matches,
            }

        candidates: List[Dict[str, Any]] = self._candidates(
            terms=terms,
            normalized_lemma=normalized_lemma,
            language=language,
        )
        if not candidates:
            raise LookupError(
                f"No ontology term matches lemma '{lemma}' in language "
                f"'{language}', neither exactly nor as a candidate."
            )
        return {
            "match_type": self.CANDIDATE_MATCH_TYPE,
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    @classmethod
    def _exact_matches(
        cls,
        *,
        terms: List[Dict[str, Any]],
        normalized_lemma: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        exact_matches: List[Dict[str, Any]] = []
        term: Dict[str, Any]
        for term in terms:
            label_language: str
            label_text: str
            for label_language, label_text in cls._labels(term, language):
                if cls._normalize(label_text) != normalized_lemma:
                    continue
                exact_matches.append(
                    {
                        "iri": term["iri"],
                        "label": label_text,
                        "label_language": label_language,
                        "ontology_prefix": term["ontology_prefix"],
                        "ontology_type": term["ontology_type"],
                        "term_type": term["term_type"],
                    }
                )
                break
        exact_matches.sort(
            key=lambda item: (item["ontology_prefix"], item["iri"])
        )
        return exact_matches

    @classmethod
    def _candidates(
        cls,
        *,
        terms: List[Dict[str, Any]],
        normalized_lemma: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        term: Dict[str, Any]
        for term in terms:
            best_label: Optional[Tuple[str, str]] = None
            best_score: float = 0.0
            label_language: str
            label_text: str
            for label_language, label_text in cls._labels(term, language):
                score: Optional[float] = cls._fuzzy_score(
                    normalized_lemma,
                    cls._normalize(label_text),
                )
                if score is None or score < cls.MIN_FUZZY_SCORE:
                    continue
                if best_label is None or score > best_score:
                    best_label = (label_language, label_text)
                    best_score = score
            if best_label is None:
                continue
            candidates.append(
                {
                    "iri": term["iri"],
                    "label": best_label[1],
                    "label_language": best_label[0],
                    "ontology_prefix": term["ontology_prefix"],
                    "ontology_type": term["ontology_type"],
                    "term_type": term["term_type"],
                    "score": best_score,
                }
            )
        candidates.sort(
            key=lambda item: (-item["score"], item["ontology_prefix"], item["iri"])
        )
        return candidates[: cls.TOP_N]

    @staticmethod
    def _labels(term: Dict[str, Any], language: str) -> List[Tuple[str, str]]:
        """Return the labels in the identified language, plus untagged ones."""
        primary_language: str = language.strip().lower().split("-", 1)[0]
        labels: List[Tuple[str, str]] = []
        label_language: str
        values: List[str]
        for label_language, values in term["labels"].items():
            if (
                label_language != OntologyDictionaryTermExtractor.UNTAGGED_LANGUAGE
                and label_language.split("-", 1)[0] != primary_language
            ):
                continue
            value: str
            for value in values:
                labels.append((label_language, value))
        return labels

    @staticmethod
    def _normalize(value: str) -> str:
        casefolded: str = value.strip().casefold()
        decomposed: str = unicodedata.normalize("NFKD", casefolded)
        no_marks: str = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        return " ".join(no_marks.split())

    @staticmethod
    def _fuzzy_score(left: str, right: str) -> Optional[float]:
        if left == right or (left not in right and right not in left):
            return None
        return float(min(len(left), len(right))) / float(max(len(left), len(right)))
