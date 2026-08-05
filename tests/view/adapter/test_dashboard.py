from pathlib import Path
from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.storage.adapter.bootstrap import CT, OBDC
from ontobdc.view.adapter.dashboard import (
    generate_project_dashboard,
    is_project_dashboard_generated,
)


class FakeContext:
    def __init__(self, **parameters: Any) -> None:
        self._parameters: Dict[str, Any] = dict(parameters)

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def has_parameter(self, name: str) -> bool:
        return name in self._parameters


def test_generates_approved_infobim_dashboard(tmp_path: Path) -> None:
    container_path = tmp_path / "techcenter-doc"
    metadata_dir = container_path / ".__ontobdc__"
    infobim_dir = metadata_dir / "__infobim__"
    infobim_dir.mkdir(parents=True)

    container_subject = URIRef(
        "urn:ontobdc:storage/local/techcenter-doc"
    )
    container_graph = Graph()
    container_graph.add((container_subject, RDF.type, OBDC.DataContainer))
    container_graph.add(
        (
            container_subject,
            DCTERMS.identifier,
            Literal(str(container_subject)),
        )
    )
    container_graph.add(
        (
            container_subject,
            DCTERMS.title,
            Literal("Storage Container: techcenter-doc"),
        )
    )
    container_graph.add(
        (
            container_subject,
            CT.description,
            Literal("Local storage container"),
        )
    )
    container_graph.serialize(
        destination=metadata_dir / "container.ttl",
        format="turtle",
    )

    project_subject = URIRef(
        "urn:infobim:project:Real%20Estate%20Brazil"
    )
    ifcowl = Namespace("http://ifcowl.openbimstandards.org/IFC4#")
    project_graph = Graph()
    project_graph.add((project_subject, RDF.type, ifcowl.IfcProject))
    project_graph.add(
        (
            project_subject,
            DCTERMS.identifier,
            Literal(str(project_subject)),
        )
    )
    project_graph.add(
        (
            project_subject,
            DCTERMS.title,
            Literal("Real Estate Brazil (Official)-Obras"),
        )
    )
    project_graph.serialize(
        destination=infobim_dir / "project.ttl",
        format="turtle",
    )

    document = container_path / "documents" / "example.pdf"
    document.parent.mkdir()
    document.write_bytes(b"%PDF-1.4\n")

    context = FakeContext(
        container_path=str(container_path),
        view_type="standard",
        representation="html",
        language="pt-br",
    )

    result = generate_project_dashboard(context)
    index_path = Path(result["index_path"])
    html = index_path.read_text(encoding="utf-8")

    assert index_path.is_file()
    assert "InfoBIM Dashboard" in html
    assert "Real Estate Brazil (Official)-Obras" in html
    assert str(project_subject) in html
    assert "Frentes de Trabalho" in html
    assert "Project Information" in html
    assert "Arquivos indexados" in html
    assert ">128<" not in html
    assert 'data-card="numeric-data-card"' not in html
    assert 'data-card="numeric-data-grid"></aside>' in html
    assert ">Pranchas<" not in html
    assert ">Documentos<" not in html
    assert ">Fotos<" not in html
    assert ">Mensagens<" not in html
    assert ">WorkStream<" in html
    assert "Pyodide Runtime" in html
    assert "Storage Container:" not in html
    assert "ontobdc-view-template" in html
    assert is_project_dashboard_generated(context)
