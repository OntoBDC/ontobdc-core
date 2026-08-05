from pathlib import Path
from typing import Any, List

from rdflib import Graph


class EntityInstanceRepositorySupport:
    def _load_turtle_graph(self, *, file_path: Path, label: str) -> Graph:
        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))

        graph: Graph = Graph()
        try:
            graph.parse(str(file_path), format="turtle")
        except Exception as exc:
            raise ValueError(f"Could not read {label}: {file_path}") from exc
        return graph

    def _references_match(self, left: Any, right: Any) -> bool:
        left_value: str = str(left or "").strip()
        right_value: str = str(right or "").strip()
        if not left_value or not right_value:
            return False
        if left_value == right_value:
            return True
        return self._normalized_reference(
            left_value
        ) == self._normalized_reference(right_value)

    def _normalized_reference(self, value: Any) -> str:
        return "".join(
            character
            for character in self._local_name(value).lower()
            if character.isalnum()
        )

    def _local_name(self, value: Any) -> str:
        raw_value: str = str(value or "").strip()
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1].strip()
        return raw_value.rstrip("/").rsplit("/", 1)[-1].strip()

    def _column_name(self, identifier: str) -> str:
        return "".join(
            part[:1].upper() + part[1:]
            for part in identifier.split("_")
            if part
        )

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
