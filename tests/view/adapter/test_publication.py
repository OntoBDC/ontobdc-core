import json
from pathlib import Path
from typing import Any, Dict

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from ontobdc.storage.adapter.bootstrap import CT, OBDC
from ontobdc.view.adapter.publication import (
    ensure_publishable,
    gather_view_data,
    generate_container_view,
    is_data_gathered,
    is_generated,
    is_publishable,
)
from ontobdc.view.adapter.publishability import is_container_publishable


class FakeContext:
    def __init__(self, root_path: Path, **parameters: Any) -> None:
        self._root_path = root_path
        self._parameters: Dict[str, Any] = dict(parameters)

    @property
    def root_path(self) -> str:
        return str(self._root_path)

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def has_parameter(self, name: str) -> bool:
        return name in self._parameters


def _make_container(tmp_path: Path) -> Path:
    container_path = tmp_path / "container"
    metadata_dir = container_path / ".__ontobdc__"
    metadata_dir.mkdir(parents=True)

    subject = URIRef("urn:ontobdc:storage/local/container")
    graph = Graph()
    graph.add((subject, RDF.type, OBDC.DataContainer))
    graph.add((subject, DCTERMS.identifier, Literal(str(subject))))
    graph.add((subject, DCTERMS.title, Literal("Test Container")))
    graph.add((subject, CT.description, Literal("Publication test")))
    graph.add(
        (
            subject,
            CT.creationDate,
            Literal(
                "2026-08-03T00:00:00+00:00",
                datatype=XSD.dateTime,
            ),
        )
    )
    graph.add((subject, PROV.atLocation, URIRef(container_path.as_uri())))
    graph.serialize(
        destination=metadata_dir / "container.ttl",
        format="turtle",
    )

    document_path = container_path / "documents" / "example.txt"
    document_path.parent.mkdir()
    document_path.write_text("first version", encoding="utf-8")
    return container_path


def _context(tmp_path: Path, container_path: Path) -> FakeContext:
    return FakeContext(
        tmp_path,
        container_path=str(container_path),
        view_type="standard",
        representation="html",
        language="pt-br",
    )


def test_publication_pipeline_regenerates_when_source_changes(
    tmp_path: Path,
) -> None:
    container_path = _make_container(tmp_path)
    context = _context(tmp_path, container_path)

    publishable_result = ensure_publishable(context)
    assert publishable_result["local_resource_count"] == 1
    assert is_publishable(context)
    assert is_container_publishable(context)

    payload = gather_view_data(context)
    assert payload["summary"]["indexed_files"] == 1
    assert is_data_gathered(context)

    generated = generate_container_view(context)
    index_path = Path(generated["index_path"])
    assert index_path.is_file()
    assert is_generated(context)

    html = index_path.read_text(encoding="utf-8")
    assert 'name="ontobdc-source-fingerprint"' in html
    assert "grid-template-columns: repeat(12" in html
    assert "Test Container" in html

    source = container_path / "documents" / "example.txt"
    source.write_text("second version", encoding="utf-8")
    assert not is_data_gathered(context)
    assert not is_generated(context)

    regenerate_result = generate_container_view(context)
    assert Path(regenerate_result["index_path"]).is_file()
    assert is_generated(context)


def test_publishability_ignores_external_resources(
    tmp_path: Path,
) -> None:
    container_path = _make_container(tmp_path)
    context = _context(tmp_path, container_path)
    ensure_publishable(context)

    datapackage_path = (
        container_path / ".__ontobdc__" / "datapackage.json"
    )
    descriptor = json.loads(datapackage_path.read_text(encoding="utf-8"))
    descriptor["resources"].append(
        {
            "name": "external_reference",
            "path": "https://example.org/reference.json",
        }
    )
    datapackage_path.write_text(
        json.dumps(descriptor, indent=2) + "\n",
        encoding="utf-8",
    )

    assert is_container_publishable(context)
