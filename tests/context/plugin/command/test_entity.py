from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.context.adapter.entity_catalog import (
    BrasidataEntityCatalogRepositoryAdapter,
)
from ontobdc.context.plugin.command.entity import ContextEntityCommand


class FakeContext:
    def __init__(self, root_path: Path, **parameters: Any) -> None:
        self._root_path: Path = root_path
        self._parameters: Dict[str, Any] = dict(parameters)

    @property
    def root_path(self) -> str:
        return str(self._root_path)

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value


def _request(
    context: FakeContext,
    arguments: List[str],
) -> CliCommandRequest:
    return CliCommandRequest(
        logical_component="context",
        component_action="entity",
        command_args=arguments,
        context=context,
    )


def test_accepts_entity_all_catalog_request() -> None:
    assert ContextEntityCommand.accepts(
        ["context", "--entity", "--all"]
    )


def test_preserves_regular_entity_lookup() -> None:
    assert ContextEntityCommand.accepts(
        [
            "context",
            "--entity",
            "http://example.com/type.ttl#Person",
        ]
    )


def test_lists_all_brasidatacenter_entities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    arguments = ["--entity", "--all"]
    context = FakeContext(root_path=tmp_path)
    expected_entities = [
        {
            "entity_uri": "http://example.com/type.ttl#Person",
            "entity_name": "Person",
            "entity_identifier": "person",
        }
    ]

    monkeypatch.setattr(
        BrasidataEntityCatalogRepositoryAdapter,
        "list_entities",
        lambda _self: {
            "source_repository": "Brasidata/brasidatacenter",
            "source_ref": "master",
            "cache_root": str(tmp_path / ".__ontobdc__" / "cache"),
            "cached_ontology_file_count": 3,
            "facade_file_count": 1,
            "entity_count": 1,
            "entities": expected_entities,
        },
    )

    command = ContextEntityCommand(_request(context, arguments))

    assert command.check()
    response = command.run()

    assert response.title == "Brasidata Entity Catalog"
    assert response.content["source_repository"] == (
        "Brasidata/brasidatacenter"
    )
    assert response.content["entity_count"] == 1
    assert response.content["entities"] == expected_entities
