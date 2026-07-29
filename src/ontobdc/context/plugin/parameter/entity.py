from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ontobdc.shared.adapter.util import is_valid_uri, to_lemma
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class EntityUriStrategy(ParameterPort, CliContextStrategyPort):
    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.context.capability.incoming.entity",
        version="0.1.0",
        name="entity",
        description="Resolve the target entity identifier to a URI reference.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=URIRef,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_entity_value: str = str(context.get_parameter_value("entity") or "").strip()
        if not raw_entity_value:
            return context

        if self._is_valid_entity_uri(raw_entity_value):
            context.set_parameter_value("entity_uri", URIRef(raw_entity_value))
            return context

        raw_entity_value: str = to_lemma(
            raw_entity_value,
            language=str(context.language or "en"),
        )
        if not raw_entity_value:
            return context

        resolved_entity_value: Optional[str] = self._resolve_entity_from_aliases(context, raw_entity_value)
        if not resolved_entity_value:
            return context

        if self._is_valid_entity_uri(resolved_entity_value):
            context.set_parameter_value("entity_uri", URIRef(resolved_entity_value))
            return context

        context.set_parameter_value("entity_uri", resolved_entity_value)

        return context

    def _is_valid_entity_uri(self, value: str) -> bool:
        normalized_value: str = str(value or "").strip()
        if not normalized_value:
            return False

        if "://" not in normalized_value and not normalized_value.startswith("urn:"):
            return False

        return bool(is_valid_uri(normalized_value))

    def _resolve_entity_from_aliases(
        self,
        context: CliContextPort,
        raw_entity_value: str,
    ) -> Optional[str]:
        entity_candidates: List[Dict[str, Any]] = self._collect_entity_candidates(context)
        if not entity_candidates:
            return None

        if len(entity_candidates) == 1:
            return entity_candidates[0]["entity_uri"]

        raise ValueError(f"Multiple entity candidates found for alias: {raw_entity_value}")

    def _collect_entity_candidates(self, context: CliContextPort) -> List[Dict[str, Any]]:
        # seen_keys: Set[str] = set()
        candidates: List[Dict[str, Any]] = []

        for candidate in self._collect_context_candidates(context) + self._collect_registered_candidates(context):
    #         entity_value: str = str(candidate.get("entity_uri") or "").strip()
    #         if not entity_value:
    #             continue

    #         aliases: List[str] = [
    #             str(alias).strip()
    #             for alias in list(candidate.get("aliases", []))
    #             if str(alias).strip()
    #         ]
    #         if not aliases:
    #             continue

    #         candidate_key: str = entity_value
    #         if candidate_key in seen_keys:
    #             continue

    #         seen_keys.add(candidate_key)
            candidates.append(candidate)

        return candidates

    #     exact_matches: List[str] = self._match_entity_candidates(entity_candidates, entity_lemma, exact_only=True)
    #     if len(exact_matches) == 1:
    #         return exact_matches[0]

    #     contains_matches: List[str] = self._match_entity_candidates(entity_candidates, entity_lemma, exact_only=False)
    #     if len(contains_matches) == 1:
    #         return contains_matches[0]

        return None

    def _collect_context_candidates(self, context: CliContextPort) -> List[Dict[str, Any]]:
        config_adapter: ConfigDataAdapter = ConfigDataAdapter()
        ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(config_adapter)
        obdc_namespace: Optional[Any] = ontology_adapter.get_ontology_namespace_by_prefix("obdc")
        if obdc_namespace is None:
            return []

        entity_alias: URIRef = obdc_namespace["entityAlias"]

        context_graph: Graph = Graph()
        context_file_path: Path = Path(context.root_path)  / ".__ontobdc__" / "context.ttl"
        context_graph.parse(context_file_path, format="turtle")

        candidates: List[Dict[str, Any]] = []

        for subject in set(context_graph.subjects(entity_alias, None)):
            if is_valid_uri(str(subject)):
                candidates.append(
                    {
                        "entity_uri": str(subject),
                        "entity_ref": subject,
                    }
                )

        return candidates

        # ontology_graph: Graph = ontology_adapter.get_ontology_content("obdc")
        # subject: URIRef
        # for subject in set(ontology_graph.subjects(entity_alias, None)):
        #     if (subject, RDF.type, data_entity_class) not in ontology_graph:
        #         continue

    #         aliases: List[str] = [
    #             self._local_name(str(subject)),
    #         ]

    #         entity_alias_object: Any
    #         for entity_alias_object in ontology_graph.objects(subject, entity_alias):
    #             entity_alias_value: str = self._object_to_string(entity_alias_object)
    #             if not entity_alias_value:
    #                 continue
    #             aliases.append(entity_alias_value)

    #         candidates.append(
    #             {
    #                 "entity_uri": str(subject),
    #                 "aliases": aliases,
    #             }
    #         )

    def _collect_registered_candidates(self, context: CliContextPort) -> List[Dict[str, Any]]:
    #     repository: EntityVectorRepositoryAdapter = EntityVectorRepositoryAdapter(str(context.root_path))
    #     origins: Dict[str, Any] = repository.resolve_origins()
    #     vector_files: List[str] = [
    #         str(vector_file).strip()
    #         for vector_file in list(origins.get("vector_files", []))
    #         if str(vector_file).strip()
    #     ]
    #     if not vector_files:
    #         return []

    #     payload: Dict[str, Any] = repository.load_registered_candidates(vector_files)
    #     raw_candidates: List[Dict[str, Any]] = list(payload.get("candidates", []))
        candidates: List[Dict[str, Any]] = []

    #     raw_candidate: Dict[str, Any]
    #     for raw_candidate in raw_candidates:
    #         entity_uri_value: str = str(raw_candidate.get("entity_type_uri") or "").strip()
    #         if not entity_uri_value:
    #             continue

    #         aliases: List[str] = [
    #             str(raw_candidate.get("identifier") or "").strip(),
    #             str(raw_candidate.get("name") or "").strip(),
    #             self._local_name(str(raw_candidate.get("candidate_uri") or "").strip()),
    #             self._local_name(entity_uri_value),
    #         ]

    #         candidates.append(
    #             {
    #                 "entity_uri": entity_uri_value,
    #                 "aliases": aliases,
    #             }
    #         )

        return candidates

    # def _match_entity_candidates(
    #     self,
    #     entity_candidates: List[Dict[str, Any]],
    #     entity_lemma: str,
    #     exact_only: bool,
    # ) -> List[str]:
    #     matched_entities: List[str] = []
    #     seen_entities: Set[str] = set()

    #     candidate: Dict[str, Any]
    #     for candidate in entity_candidates:
    #         entity_uri_value: str = str(candidate.get("entity_uri") or "").strip()
    #         if not entity_uri_value:
    #             continue

    #         aliases: List[str] = list(candidate.get("aliases", []))
    #         alias: str
    #         for alias in aliases:
    #             alias_lemma: str = self._to_lemma(alias)
    #             if not alias_lemma:
    #                 continue

    #             if exact_only and alias_lemma != entity_lemma:
    #                 continue

    #             if not exact_only and entity_lemma not in alias_lemma.split():
    #                 continue

    #             if entity_uri_value in seen_entities:
    #                 break

    #             seen_entities.add(entity_uri_value)
    #             matched_entities.append(entity_uri_value)
    #             break

    #     return matched_entities

    # def _local_name(self, value: str) -> str:
    #     normalized_value: str = str(value or "").strip()
    #     if not normalized_value:
    #         return ""

    #     if "#" in normalized_value:
    #         return normalized_value.rsplit("#", 1)[-1].strip()

    #     return normalized_value.rstrip("/").rsplit("/", 1)[-1].strip()

    # def _object_to_string(self, obj: Any) -> str:
    #     if isinstance(obj, Literal):
    #         return str(obj.toPython()).strip()

    #     return str(obj).strip()
