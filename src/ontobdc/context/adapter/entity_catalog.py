from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph, Literal, URIRef

from ontobdc.context.adapter.vector import EntityVectorRepositoryAdapter


class BrasidataEntityCatalogRepositoryAdapter:
    """Read the public entity facade catalog published by brasidatacenter."""

    def __init__(
        self,
        root_path: str,
        vector_repository: Optional[EntityVectorRepositoryAdapter] = None,
    ) -> None:
        self._root_path: Path = Path(root_path).expanduser().resolve()
        self._vector_repository: EntityVectorRepositoryAdapter = (
            vector_repository
            or EntityVectorRepositoryAdapter(root_path=str(self._root_path))
        )

    def list_entities(self) -> Dict[str, Any]:
        sync_payload: Dict[str, Any] = (
            self._vector_repository.sync_remote_ontology_vector_cache()
        )
        cache_root: Path = Path(
            str(sync_payload.get("cache_root") or "")
        ).expanduser().resolve()
        facade_files: List[Path] = sorted(
            file_path
            for file_path in (cache_root / "ontology").rglob("facade.ttl")
            if file_path.is_file()
        )
        entities: List[Dict[str, Any]] = self._load_entities(
            cache_root=cache_root,
            facade_files=facade_files,
        )

        remote_owner: str = str(
            self._vector_repository.REMOTE_OWNER
        ).strip()
        remote_repository: str = str(
            self._vector_repository.REMOTE_REPOSITORY
        ).strip()
        remote_ref: str = str(
            sync_payload.get("remote_ontology_ref")
            or self._vector_repository.REMOTE_ONTOLOGY_REF
        ).strip()

        return {
            "source_repository": f"{remote_owner}/{remote_repository}",
            "source_ref": remote_ref,
            "cache_root": str(cache_root),
            "cached_ontology_file_count": int(
                len(list(sync_payload.get("cached_ontology_files") or []))
            ),
            "facade_file_count": len(facade_files),
            "entity_count": len(entities),
            "entities": entities,
        }

    def _load_entities(
        self,
        *,
        cache_root: Path,
        facade_files: List[Path],
    ) -> List[Dict[str, Any]]:
        selected_by_uri: Dict[str, Dict[str, Any]] = {}

        for facade_file in facade_files:
            graph: Graph = Graph()
            graph.parse(str(facade_file), format="turtle")
            relative_source_path: str = self._relative_source_path(
                cache_root=cache_root,
                source_file=facade_file,
            )

            entity_subject: URIRef
            predicate: URIRef
            facade_subject: URIRef
            for entity_subject, predicate, facade_subject in graph:
                if self._local_name(predicate) != "hasDataEntityFacade":
                    continue
                if not isinstance(entity_subject, URIRef):
                    continue
                if not isinstance(facade_subject, URIRef):
                    continue

                entity_uri: str = str(entity_subject).strip()
                if not entity_uri:
                    continue

                entity_record: Dict[str, Any] = {
                    "entity_uri": entity_uri,
                    "entity_name": self._local_name(entity_subject),
                    "entity_identifier": self._snake_case(
                        self._local_name(entity_subject)
                    ),
                    "facade_uri": str(facade_subject),
                    "facade_identifier": self._literal_value(
                        graph=graph,
                        subject=facade_subject,
                        predicate_local_name="identifier",
                    ),
                    "facade_name": self._literal_value(
                        graph=graph,
                        subject=facade_subject,
                        predicate_local_name="name",
                    ),
                    "description": self._literal_value(
                        graph=graph,
                        subject=facade_subject,
                        predicate_local_name="description",
                    ),
                    "field_count": self._count_objects(
                        graph=graph,
                        subject=facade_subject,
                        predicate_local_name="hasFacadeField",
                    ),
                    "domain": self._ontology_domain(relative_source_path),
                    "kind": self._ontology_kind(relative_source_path),
                    "source_path": relative_source_path,
                }

                current_record: Optional[Dict[str, Any]] = (
                    selected_by_uri.get(entity_uri)
                )
                if current_record is None or relative_source_path < str(
                    current_record.get("source_path") or ""
                ):
                    selected_by_uri[entity_uri] = entity_record

        return sorted(
            selected_by_uri.values(),
            key=lambda entity: (
                str(entity.get("domain") or ""),
                str(entity.get("entity_identifier") or ""),
                str(entity.get("entity_uri") or ""),
            ),
        )

    def _literal_value(
        self,
        *,
        graph: Graph,
        subject: URIRef,
        predicate_local_name: str,
    ) -> str:
        predicate: URIRef
        obj: Any
        for predicate, obj in graph.predicate_objects(subject):
            if self._local_name(predicate) != predicate_local_name:
                continue
            if isinstance(obj, Literal):
                return str(obj).strip()

        return ""

    def _count_objects(
        self,
        *,
        graph: Graph,
        subject: URIRef,
        predicate_local_name: str,
    ) -> int:
        return sum(
            1
            for predicate, _ in graph.predicate_objects(subject)
            if self._local_name(predicate) == predicate_local_name
        )

    def _relative_source_path(
        self,
        *,
        cache_root: Path,
        source_file: Path,
    ) -> str:
        try:
            return source_file.relative_to(cache_root).as_posix()
        except ValueError:
            return source_file.as_posix()

    def _ontology_domain(self, source_path: str) -> str:
        path_parts: List[str] = list(Path(source_path).parts)
        if len(path_parts) >= 2 and path_parts[0] == "ontology":
            return path_parts[1]
        return ""

    def _ontology_kind(self, source_path: str) -> str:
        path_parts: List[str] = list(Path(source_path).parts)
        if len(path_parts) >= 3 and path_parts[0] == "ontology":
            return path_parts[2]
        return ""

    def _snake_case(self, value: str) -> str:
        output: List[str] = []
        for index, character in enumerate(value):
            if (
                character.isupper()
                and index
                and value[index - 1].islower()
            ):
                output.append("_")
            output.append(character.lower())
        return "".join(output)

    def _local_name(self, uri: Any) -> str:
        raw_value: str = str(uri).strip()
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1]
        return raw_value.rstrip("/").rsplit("/", 1)[-1]
