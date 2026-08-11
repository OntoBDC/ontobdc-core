from pathlib import Path
from typing import Any, Dict

from ontobdc.context.adapter.entity_catalog import (
    BrasidataEntityCatalogRepositoryAdapter,
)


class FakeVectorRepository:
    REMOTE_OWNER = "Brasidata"
    REMOTE_REPOSITORY = "brasidatacenter"
    REMOTE_ONTOLOGY_REF = "master"

    def __init__(self, cache_root: Path) -> None:
        self._cache_root: Path = cache_root

    def sync_remote_ontology_vector_cache(self) -> Dict[str, Any]:
        cached_files = [
            str(file_path)
            for file_path in self._cache_root.rglob("*.ttl")
            if file_path.is_file()
        ]
        return {
            "remote_ontology_ref": self.REMOTE_ONTOLOGY_REF,
            "cache_root": str(self._cache_root),
            "cached_ontology_files": cached_files,
        }


def _write_facade(
    path: Path,
    *,
    entity_uri: str,
    facade_uri: str,
    identifier: str,
    name: str,
    description: str,
    field_count: int,
) -> None:
    fields = ",\n        ".join(
        f"<{facade_uri}/field/{index}>"
        for index in range(field_count)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "@prefix ex: <http://example.com/facade#> .",
                "@prefix schema: <https://schema.org/> .",
                "",
                f"<{entity_uri}> ex:hasDataEntityFacade <{facade_uri}> .",
                "",
                f"<{facade_uri}> schema:identifier \"{identifier}\" ;",
                f"    schema:name \"{name}\"@en ;",
                f"    schema:description \"{description}\"@en"
                + (
                    " ;\n    ex:hasFacadeField " + fields + " ."
                    if fields
                    else " ."
                ),
            ]
        ),
        encoding="utf-8",
    )


def test_lists_entity_facades_from_cached_brasidatacenter(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / ".__ontobdc__" / "cache"
    _write_facade(
        cache_root / "ontology/social/entity/person/facade.ttl",
        entity_uri=(
            "http://datacenter.app.br/ontology/social/entity/person/"
            "type.ttl#Person"
        ),
        facade_uri=(
            "http://datacenter.app.br/ontology/social/entity/person/"
            "facade.ttl#PersonFacade"
        ),
        identifier="person_facade",
        name="Person Facade",
        description="Public facade for people.",
        field_count=2,
    )
    _write_facade(
        cache_root / "ontology/productivity/entity/work_stream/facade.ttl",
        entity_uri=(
            "http://datacenter.app.br/ontology/productivity/entity/"
            "work_stream/type.ttl#WorkStream"
        ),
        facade_uri=(
            "http://datacenter.app.br/ontology/productivity/entity/"
            "work_stream/facade.ttl#WorkStreamFacade"
        ),
        identifier="work_stream_facade",
        name="WorkStream Facade",
        description="Public facade for work streams.",
        field_count=3,
    )

    repository = BrasidataEntityCatalogRepositoryAdapter(
        root_path=str(tmp_path),
        vector_repository=FakeVectorRepository(cache_root),
    )

    payload = repository.list_entities()

    assert payload["source_repository"] == "Brasidata/brasidatacenter"
    assert payload["source_ref"] == "master"
    assert payload["facade_file_count"] == 2
    assert payload["entity_count"] == 2
    assert [
        entity["entity_identifier"]
        for entity in payload["entities"]
    ] == ["work_stream", "person"]
    assert payload["entities"][0]["domain"] == "productivity"
    assert payload["entities"][0]["kind"] == "entity"
    assert payload["entities"][0]["field_count"] == 3
    assert payload["entities"][1]["facade_identifier"] == "person_facade"
    assert payload["entities"][1]["description"] == (
        "Public facade for people."
    )
