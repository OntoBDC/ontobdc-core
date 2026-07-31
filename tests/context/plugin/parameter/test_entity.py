from pathlib import Path
from typing import Any, Dict
from urllib.error import URLError

import pytest
from rdflib import URIRef

import ontobdc.context.plugin.parameter.entity as entity_module
from ontobdc.context.plugin.parameter.entity import EntityUriStrategy


class _Context:
    def __init__(
        self,
        root_path: Path,
        parameters: Dict[str, Any],
    ) -> None:
        self._root_path: Path = root_path
        self._parameters: Dict[str, Any] = dict(parameters)

    @property
    def root_path(self) -> str:
        return str(self._root_path)

    @property
    def language(self) -> None:
        return None

    def get_parameter_value(self, key: str) -> Any:
        return self._parameters.get(key)

    def set_parameter_value(self, key: str, value: Any) -> None:
        self._parameters[key] = value


def _write_context_ttl(tmp_path: Path, content: str) -> Path:
    context_file: Path = tmp_path / ".__ontobdc__" / "context.ttl"
    context_file.parent.mkdir(parents=True, exist_ok=True)
    context_file.write_text(content, encoding="utf-8")
    return context_file


def test_valid_uri_is_only_validated_and_preserved(tmp_path, monkeypatch) -> None:
    strategy = EntityUriStrategy()
    context = _Context(
        tmp_path,
        {"entity": "https://example.org/ontology#WorkStream"},
    )

    def fail_alias_resolution(*_args, **_kwargs):
        raise AssertionError("Alias resolution must not run for a URI.")

    monkeypatch.setattr(
        strategy,
        "_resolve_entity_from_aliases",
        fail_alias_resolution,
    )

    strategy.execute(context)

    assert context.get_parameter_value("entity_uri") == URIRef(
        "https://example.org/ontology#WorkStream"
    )


def test_invalid_uri_is_rejected_without_alias_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    strategy = EntityUriStrategy()
    context = _Context(
        tmp_path,
        {"entity": "https://example .org/invalid"},
    )

    def fail_alias_resolution(*_args, **_kwargs):
        raise AssertionError("Invalid URI must not be treated as an alias.")

    monkeypatch.setattr(
        strategy,
        "_resolve_entity_from_aliases",
        fail_alias_resolution,
    )

    with pytest.raises(ValueError, match="Invalid entity URI"):
        strategy.execute(context)


@pytest.mark.parametrize(
    ("raw_entity", "expected_local_name"),
    [
        ("IfcTask", "IfcTask"),
        ("ifcTask", "IfcTask"),
        ("IFCWall", "IfcWall"),
        ("iFcDoor", "IfcDoor"),
    ],
)
def test_ifc_prefix_is_case_insensitive(
    tmp_path,
    raw_entity,
    expected_local_name,
) -> None:
    strategy = EntityUriStrategy()
    context = _Context(tmp_path, {"entity": raw_entity})

    strategy.execute(context)

    assert context.get_parameter_value("entity_uri") == URIRef(
        f"http://ifcowl.openbimstandards.org/IFC4#{expected_local_name}"
    )


def test_context_alias_is_resolved_before_remote_registry(
    tmp_path,
    monkeypatch,
) -> None:
    _write_context_ttl(
        tmp_path,
        """
@prefix obdc: <http://ontobdc.org/ontology/domain/ns.ttl#> .

<https://example.org/context#WorkStream>
    obdc:entityAlias "Work Stream", "work_stream" .
""".strip(),
    )
    strategy = EntityUriStrategy()
    context = _Context(tmp_path, {"entity": "WORK-STREAM"})

    def fail_remote_load(_context):
        raise AssertionError(
            "Brasidatacenter must not be loaded after a context match."
        )

    monkeypatch.setattr(
        strategy,
        "_load_brasidatacenter_index",
        fail_remote_load,
    )

    strategy.execute(context)

    assert context.get_parameter_value("entity_uri") == URIRef(
        "https://example.org/context#WorkStream"
    )


def test_brasidatacenter_alias_is_resolved_from_yaml_structure(
    tmp_path,
    monkeypatch,
) -> None:
    strategy = EntityUriStrategy()
    context = _Context(tmp_path, {"entity": "Sales Opportunity"})
    monkeypatch.setattr(
        strategy,
        "_load_brasidatacenter_index",
        lambda _context: {
            "entity": {
                "sales": {
                    "aliases": [
                        {
                            "salesopportunity": (
                                "http://datacenter.app.br/ontology/sales/"
                                "entity/sales_opportunity/type.ttl"
                                "#SalesOpportunity"
                            )
                        },
                        {
                            "sales_opportunity": (
                                "http://datacenter.app.br/ontology/sales/"
                                "entity/sales_opportunity/type.ttl"
                                "#SalesOpportunity"
                            )
                        },
                    ]
                }
            }
        },
    )

    strategy.execute(context)

    assert context.get_parameter_value("entity_uri") == URIRef(
        "http://datacenter.app.br/ontology/sales/"
        "entity/sales_opportunity/type.ttl#SalesOpportunity"
    )


def test_ambiguous_context_alias_is_rejected(tmp_path) -> None:
    _write_context_ttl(
        tmp_path,
        """
@prefix obdc: <http://ontobdc.org/ontology/domain/ns.ttl#> .

<https://example.org/context#First>
    obdc:entityAlias "duplicate" .

<https://example.org/context#Second>
    obdc:entityAlias "duplicate" .
""".strip(),
    )
    strategy = EntityUriStrategy()
    context = _Context(tmp_path, {"entity": "duplicate"})

    with pytest.raises(ValueError, match="ambiguous in context.ttl"):
        strategy.execute(context)


def test_unknown_alias_is_rejected(tmp_path, monkeypatch) -> None:
    strategy = EntityUriStrategy()
    context = _Context(tmp_path, {"entity": "DoesNotExist"})
    monkeypatch.setattr(
        strategy,
        "_load_brasidatacenter_index",
        lambda _context: {"entity": {}},
    )

    with pytest.raises(ValueError, match="was not found"):
        strategy.execute(context)


def test_cached_brasidatacenter_yaml_is_used_when_remote_is_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    cache_path: Path = (
        tmp_path
        / ".__ontobdc__"
        / "cache"
        / "ontology"
        / "index.yaml"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        """
entity:
  productivity:
    aliases:
      - workstream: https://example.org/ontology#WorkStream
""".strip(),
        encoding="utf-8",
    )

    def fail_download(*_args, **_kwargs):
        raise URLError("offline")

    monkeypatch.setattr(entity_module, "urlopen", fail_download)

    strategy = EntityUriStrategy()
    context = _Context(tmp_path, {"entity": "workstream"})
    strategy.execute(context)

    assert context.get_parameter_value("entity_uri") == URIRef(
        "https://example.org/ontology#WorkStream"
    )
