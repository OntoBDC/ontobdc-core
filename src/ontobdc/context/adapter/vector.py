import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from rdflib import Graph, Literal, URIRef


class EntityVectorRepositoryAdapter:
    DEFAULT_MAX_DISTANCE: float = 0.22
    REMOTE_OWNER: str = "Brasidata"
    REMOTE_REPOSITORY: str = "brasidatacenter"
    REMOTE_ONTOLOGY_REF: str = "master"
    REMOTE_ONTOLOGY_FILENAMES = frozenset({"vector.ttl", "type.ttl", "facade.ttl"})

    def __init__(self, root_path: str):
        self._project_root: Path = Path(root_path).expanduser().resolve()

    @property
    def default_max_distance(self) -> float:
        return self.DEFAULT_MAX_DISTANCE

    @property
    def cache_root(self) -> Path:
        return self._project_root / ".__ontobdc__" / "cache"

    def resolve_origins(self) -> Dict[str, Any]:
        local_vector_files: List[Path] = sorted(
            file_path
            for file_path in self._project_root.rglob("vector.ttl")
            if file_path.is_file() and ".__ontobdc__" not in file_path.parts
        )
        cached_vector_files: List[Path] = sorted(
            file_path
            for file_path in (self.cache_root / "ontology").rglob("vector.ttl")
            if file_path.is_file()
        )
        vector_files: List[Path] = sorted({*local_vector_files, *cached_vector_files})

        return {
            "project_root": str(self._project_root),
            "cache_root": str(self.cache_root),
            "remote_ontology_ref": self.REMOTE_ONTOLOGY_REF,
            "local_vector_files": [str(file_path) for file_path in local_vector_files],
            "cached_vector_files": [str(file_path) for file_path in cached_vector_files],
            "vector_files": [str(file_path) for file_path in vector_files],
            "default_max_distance": self.default_max_distance,
        }

    def sync_remote_ontology_vector_cache(self) -> Dict[str, Any]:
        cache_files: List[str] = []
        remote_paths: List[str] = self._list_remote_ontology_paths()
        for remote_path in remote_paths:
            target_path: Path = self.cache_root / Path(remote_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                self._download_remote_text_file(remote_path),
                encoding="utf-8",
            )
            cache_files.append(str(target_path))

        return {
            "remote_ontology_ref": self.REMOTE_ONTOLOGY_REF,
            "remote_ontology_path_count": len(remote_paths),
            "remote_vector_path_count": len(
                [path for path in remote_paths if path.endswith("/vector.ttl")]
            ),
            "cached_ontology_files": cache_files,
            "cached_vector_files": [
                path for path in cache_files if path.endswith("/vector.ttl")
            ],
            "cache_root": str(self.cache_root),
        }

    def resolve_entity_facade(self, entity: str) -> Optional[Dict[str, Any]]:
        local_facade_files = sorted(
            file_path
            for file_path in self._project_root.rglob("facade.ttl")
            if file_path.is_file() and ".__ontobdc__" not in file_path.parts
        )
        resolved_facade: Optional[Dict[str, Any]] = self._resolve_entity_facade_from_files(
            entity=entity,
            facade_files=local_facade_files,
        )
        if resolved_facade is not None:
            return resolved_facade

        self.sync_remote_ontology_vector_cache()
        cached_facade_files = sorted(
            file_path
            for file_path in (self.cache_root / "ontology").rglob("facade.ttl")
            if file_path.is_file()
        )
        return self._resolve_entity_facade_from_files(
            entity=entity,
            facade_files=cached_facade_files,
        )

    def _resolve_entity_facade_from_files(
        self,
        *,
        entity: str,
        facade_files: List[Path],
    ) -> Optional[Dict[str, Any]]:
        normalized_entity = self._normalized_name(self._local_name(entity))
        for facade_file in facade_files:
            graph = Graph()
            graph.parse(str(facade_file), format="turtle")
            for entity_subject, predicate, facade_subject in graph:
                if self._local_name(predicate) != "hasDataEntityFacade":
                    continue
                if self._normalized_name(self._local_name(entity_subject)) != normalized_entity:
                    continue
                fields = []
                for _, field_predicate, field_subject in graph.triples(
                    (facade_subject, None, None)
                ):
                    if self._local_name(field_predicate) != "hasFacadeField":
                        continue
                    identifier = self._first_literal_by_local_name(
                        graph, field_subject, "identifier"
                    )
                    datatype = self._first_object_by_local_name(
                        graph, field_subject, "fieldDatatype"
                    )
                    if identifier is None:
                        continue
                    fields.append(
                        {
                            "identifier": str(identifier),
                            "name": self._column_name(str(identifier)),
                            "datatype": self._local_name(datatype) if datatype else "string",
                        }
                    )
                fields.sort(
                    key=lambda field: (
                        0 if field["identifier"] == "global_id" else
                        1 if field["identifier"] == "name" else 2,
                        field["identifier"],
                    )
                )
                if fields:
                    return {
                        "entity_uri": str(entity_subject),
                        "entity_name": self._local_name(entity_subject),
                        "entity_identifier": self._snake_case(
                            self._local_name(entity_subject)
                        ),
                        "facade_uri": str(facade_subject),
                        "fields": fields,
                        "source_file": str(facade_file),
                    }
        return None

    def load_registered_candidates(self, file_paths: List[str]) -> Dict[str, Any]:
        ontology_payload: Dict[str, Any] = self.load_candidates(
            file_paths=file_paths, source_kind="ontology"
        )
        learning_payload: Dict[str, Any] = self.load_learning_record_candidates()
        return {
            "source_kind": "registered",
            "file_count": int(ontology_payload["file_count"]) + int(learning_payload["file_count"]),
            "candidate_count": int(ontology_payload["candidate_count"]) + int(learning_payload["candidate_count"]),
            "candidates": list(ontology_payload["candidates"]) + list(learning_payload["candidates"]),
            "max_distance": ontology_payload["max_distance"],
            "max_distance_source": ontology_payload["max_distance_source"],
        }

    def load_candidates(self, file_paths: List[str], source_kind: str) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = []
        max_distance: Optional[float] = None
        max_distance_source: Optional[str] = None
        for raw_file_path in file_paths:
            file_path = Path(raw_file_path).expanduser().resolve()
            if not file_path.is_file():
                continue
            graph = Graph()
            graph.parse(str(file_path), format="turtle")
            for subject in set(graph.subjects()):
                identifier_literal = self._first_literal_by_local_name(graph, subject, "identifier")
                identifier_value = str(identifier_literal) if identifier_literal is not None else None
                if identifier_value == "max_distance":
                    value_literal = self._first_literal_by_local_name(graph, subject, "value")
                    if value_literal is not None and max_distance is None:
                        max_distance = float(str(value_literal))
                        max_distance_source = str(file_path)
                    continue
                vector_literal = self._first_literal_by_local_name(graph, subject, "documentTypeVectorValue")
                if vector_literal is None:
                    continue
                entity_type_object = self._first_object_by_local_name(graph, subject, "isDocumentEntityTypeOf")
                supported_file_type_literal = self._first_literal_by_local_name(graph, subject, "supportedFileType")
                name_literal = self._first_literal_by_local_name(graph, subject, "name")
                description_literal = self._first_literal_by_local_name(graph, subject, "description")
                candidates.append({
                    "candidate_uri": str(subject),
                    "identifier": identifier_value or self._local_name(subject),
                    "name": str(name_literal) if name_literal is not None else self._local_name(subject),
                    "description": str(description_literal) if description_literal is not None else "",
                    "entity_type_uri": str(entity_type_object) if entity_type_object is not None else "",
                    "vector": self._parse_vector_literal(vector_literal),
                    "supported_file_type": str(supported_file_type_literal) if supported_file_type_literal is not None else "",
                    "source_kind": source_kind,
                    "source_file": str(file_path),
                })
        deduplicated_candidates = self._deduplicate_candidates(candidates)
        return {
            "source_kind": source_kind,
            "file_count": len(file_paths),
            "candidate_count": len(deduplicated_candidates),
            "candidates": deduplicated_candidates,
            "max_distance": max_distance,
            "max_distance_source": max_distance_source or "",
        }

    def load_learning_record_candidates(self) -> Dict[str, Any]:
        context_file_path = self._project_root / ".__ontobdc__" / "context.ttl"
        if not context_file_path.is_file():
            return {"source_kind": "learning_record", "file_count": 0, "candidate_count": 0, "candidates": [], "max_distance": None, "max_distance_source": ""}
        graph = Graph()
        graph.parse(str(context_file_path), format="turtle")
        candidates = []
        for subject in set(graph.subjects()):
            aligned_vector_literal = self._first_literal_by_local_name(graph, subject, "alignedVector")
            if aligned_vector_literal is None:
                continue
            entity_type_object = self._first_object_by_local_name(graph, subject, "entityUri")
            supported_file_type_literal = self._first_literal_by_local_name(graph, subject, "supportedFileType")
            source_file_path_literal = self._first_literal_by_local_name(graph, subject, "sourceFilePath")
            content_language_literal = self._first_literal_by_local_name(graph, subject, "contentLanguage")
            learned_at_literal = self._first_literal_by_local_name(graph, subject, "learnedAt")
            candidates.append({
                "candidate_uri": str(subject),
                "identifier": self._local_name(subject),
                "name": self._local_name(entity_type_object) if entity_type_object is not None else self._local_name(subject),
                "description": str(source_file_path_literal) if source_file_path_literal is not None else "",
                "entity_type_uri": str(entity_type_object) if entity_type_object is not None else "",
                "vector": self._parse_vector_literal(aligned_vector_literal),
                "supported_file_type": str(supported_file_type_literal) if supported_file_type_literal is not None else "",
                "source_kind": "learning_record",
                "source_file": str(context_file_path),
                "source_path": str(source_file_path_literal) if source_file_path_literal is not None else "",
                "content_language": str(content_language_literal) if content_language_literal is not None else "",
                "learned_at": str(learned_at_literal) if learned_at_literal is not None else "",
            })
        return {"source_kind": "learning_record", "file_count": 1, "candidate_count": len(candidates), "candidates": candidates, "max_distance": None, "max_distance_source": ""}

    def _list_remote_ontology_paths(self) -> List[str]:
        request = Request(self._remote_tree_api_url(), headers={"Accept": "application/vnd.github+json", "User-Agent": "OntoBDC"})
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return sorted(
            path
            for entry in list(payload.get("tree", []))
            if entry.get("type") == "blob"
            for path in [str(entry.get("path", "")).strip()]
            if path.startswith("ontology/")
            and Path(path).name in self.REMOTE_ONTOLOGY_FILENAMES
        )

    def _list_remote_ontology_vector_paths(self) -> List[str]:
        return [
            path for path in self._list_remote_ontology_paths()
            if path.endswith("/vector.ttl") or path == "ontology/vector.ttl"
        ]

    def _download_remote_text_file(self, remote_path: str) -> str:
        request = Request(self._remote_raw_file_url(remote_path), headers={"User-Agent": "OntoBDC"})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")

    def _remote_tree_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.REMOTE_OWNER}/{self.REMOTE_REPOSITORY}/git/trees/{self.REMOTE_ONTOLOGY_REF}?recursive=1"

    def _remote_raw_file_url(self, remote_path: str) -> str:
        return f"https://raw.githubusercontent.com/{self.REMOTE_OWNER}/{self.REMOTE_REPOSITORY}/{self.REMOTE_ONTOLOGY_REF}/{remote_path}"

    def _first_literal_by_local_name(self, graph: Graph, subject: URIRef, local_name: str) -> Optional[Literal]:
        for _, predicate, obj in graph.triples((subject, None, None)):
            if self._local_name(predicate) == local_name and isinstance(obj, Literal):
                return obj
        return None

    def _first_object_by_local_name(self, graph: Graph, subject: URIRef, local_name: str) -> Optional[URIRef]:
        for _, predicate, obj in graph.triples((subject, None, None)):
            if self._local_name(predicate) == local_name and isinstance(obj, URIRef):
                return obj
        return None

    def _parse_vector_literal(self, literal: Literal) -> List[float]:
        payload = json.loads(str(literal).strip())
        if not isinstance(payload, list):
            raise ValueError(f"Vector literal must be a JSON array, got '{literal}'.")
        return [float(value) for value in payload]

    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        selected_by_uri = {}
        for candidate in candidates:
            candidate_uri = str(candidate["candidate_uri"]).strip()
            current_candidate = selected_by_uri.get(candidate_uri)
            if current_candidate is None or self._should_replace_candidate(current_candidate, candidate):
                selected_by_uri[candidate_uri] = candidate
        return sorted(selected_by_uri.values(), key=lambda candidate: (str(candidate.get("candidate_uri", "")), str(candidate.get("source_file", ""))))

    def _should_replace_candidate(self, current_candidate: Dict[str, Any], new_candidate: Dict[str, Any]) -> bool:
        current_is_cached = self._is_cached_source_file(str(current_candidate.get("source_file", "")))
        new_is_cached = self._is_cached_source_file(str(new_candidate.get("source_file", "")))
        if current_is_cached != new_is_cached:
            return current_is_cached and not new_is_cached
        return str(new_candidate.get("source_file", "")) < str(current_candidate.get("source_file", ""))

    def _is_cached_source_file(self, source_file: str) -> bool:
        return ".__ontobdc__" in Path(source_file).parts and "cache" in Path(source_file).parts

    def _normalized_name(self, value: str) -> str:
        return "".join(character for character in value.lower() if character.isalnum())

    def _column_name(self, identifier: str) -> str:
        return "".join(part[:1].upper() + part[1:] for part in identifier.split("_"))

    def _snake_case(self, value: str) -> str:
        output = []
        for index, character in enumerate(value):
            if character.isupper() and index and value[index - 1].islower():
                output.append("_")
            output.append(character.lower())
        return "".join(output)

    def _local_name(self, uri: Any) -> str:
        raw_value = str(uri)
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1]
        if "/" in raw_value:
            return raw_value.rstrip("/").rsplit("/", 1)[-1]
        return raw_value
