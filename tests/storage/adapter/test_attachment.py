from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, XSD

from ontobdc.storage.adapter.attachment import (
    attach_container_metadata,
    attach_context,
    attach_datasets,
    attach_storage_index,
    complete_attachment,
    inspect_container,
    is_container_attached,
    is_container_metadata_attached,
    is_context_attached,
    is_datasets_attached,
    is_storage_index_attached,
    resolve_identity,
    rollback_attachment,
)


OBDC = Namespace("http://ontobdc.org/ontology/domain/ns.ttl#")
CT = Namespace(
    "http://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
)


class FakeContext:
    def __init__(self, root_path: Path, container_path: Path) -> None:
        self.root_path = str(root_path)
        self._parameters: Dict[str, Any] = {
            "container_path": str(container_path),
            "container_id": "urn:ontobdc:storage/local/stale",
            "container_update_completed": True,
            "container_html_view_updated": True,
        }

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def delete_parameter(self, name: str) -> None:
        self._parameters.pop(name, None)


def _write_imported_container(root_path: Path) -> tuple[Path, Path]:
    (root_path / ".__ontobdc__").mkdir(parents=True)
    container_path = root_path / "imported"
    dataset_path = container_path / "documents"
    (container_path / ".__ontobdc__").mkdir(parents=True)
    (dataset_path / ".__ontobdc__").mkdir(parents=True)

    old_container = URIRef("urn:ontobdc:storage/local/old")
    old_container_location = URIRef(
        (root_path.parent / "old-root" / "imported").as_uri()
    )
    old_dataset = URIRef(
        "urn:ontobdc:storage/dataset/old-root/imported/documents"
    )
    old_dataset_location = URIRef(
        (
            root_path.parent
            / "old-root"
            / "imported"
            / "documents"
        ).as_uri()
    )
    old_entity = URIRef(f"{old_dataset}/entity")
    old_ontology = URIRef(
        (
            root_path.parent
            / "old-root"
            / "imported"
            / "documents"
            / ".__ontobdc__"
            / "dataset.ttl"
        ).as_uri()
    )
    created = Literal(
        datetime.now().replace(microsecond=0).isoformat(),
        datatype=XSD.dateTime,
    )

    container_graph = Graph()
    container_graph.add((old_container, RDF.type, OBDC.DataContainer))
    container_graph.add(
        (old_container, DCTERMS.identifier, Literal(str(old_container)))
    )
    container_graph.add(
        (old_container, DCTERMS.title, Literal("Imported Container"))
    )
    container_graph.add(
        (old_container, CT.description, Literal("Imported description"))
    )
    container_graph.add((old_container, CT.creationDate, created))
    container_graph.add(
        (old_container, PROV.atLocation, old_container_location)
    )
    container_graph.add(
        (old_container, OBDC.hasEntityDataset, old_dataset)
    )
    container_graph.add((old_dataset, RDF.type, OBDC.EntityDataset))
    container_graph.add(
        (old_dataset, DCTERMS.title, Literal("Documents"))
    )
    container_graph.add(
        (old_dataset, DCTERMS.description, Literal("Documents dataset"))
    )
    container_graph.add(
        (old_dataset, PROV.atLocation, old_dataset_location)
    )
    container_graph.add(
        (old_dataset, OBDC.belongsToDataContainer, old_container)
    )
    container_graph.serialize(
        container_path / ".__ontobdc__" / "container.ttl",
        format="turtle",
    )

    dataset_graph = Graph()
    dataset_graph.add((old_ontology, RDF.type, OWL.Ontology))
    dataset_graph.add((old_dataset, RDF.type, OBDC.EntityDataset))
    dataset_graph.add(
        (old_dataset, DCTERMS.identifier, Literal(str(old_dataset)))
    )
    dataset_graph.add(
        (old_dataset, DCTERMS.title, Literal("Documents"))
    )
    dataset_graph.add(
        (old_dataset, DCTERMS.description, Literal("Documents dataset"))
    )
    dataset_graph.add((old_dataset, CT.creationDate, created))
    dataset_graph.add(
        (old_dataset, PROV.atLocation, old_dataset_location)
    )
    dataset_graph.add(
        (old_dataset, OBDC.belongsToDataContainer, old_container)
    )
    dataset_graph.add((old_dataset, OBDC.hasDataEntity, old_entity))
    dataset_graph.serialize(
        dataset_path / ".__ontobdc__" / "dataset.ttl",
        format="turtle",
    )

    storage = URIRef("urn:ontobdc:storage/local")
    storage_graph = Graph()
    storage_graph.add((storage, RDF.type, OBDC.DataStorage))
    storage_graph.add((old_container, RDF.type, OBDC.DataContainer))
    storage_graph.add(
        (old_container, DCTERMS.identifier, Literal(str(old_container)))
    )
    storage_graph.add(
        (old_container, DCTERMS.title, Literal("Imported Container"))
    )
    storage_graph.add(
        (old_container, CT.description, Literal("Imported description"))
    )
    storage_graph.add((old_container, CT.creationDate, created))
    storage_graph.add(
        (old_container, PROV.atLocation, old_container_location)
    )
    storage_graph.serialize(
        root_path / ".__ontobdc__" / "storage.ttl",
        format="turtle",
    )
    return container_path, dataset_path


def test_attach_reconciles_container_dataset_storage_and_context(
    tmp_path: Path,
) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()
    container_path, dataset_path = _write_imported_container(root_path)
    context = FakeContext(root_path, container_path)

    inspection = inspect_container(context)
    identity = resolve_identity(context)
    attach_container_metadata(context)
    attach_datasets(context)
    attach_storage_index(context)
    attach_context(context)
    result = complete_attachment(context)

    assert inspection["dataset_count"] == 1
    assert identity["target_container_id"] == (
        "urn:ontobdc:storage/local/imported"
    )
    assert result["datasets_attached"] == 1
    assert is_container_metadata_attached(context)
    assert is_datasets_attached(context)
    assert is_storage_index_attached(context)
    assert is_context_attached(context)
    assert is_container_attached(context)
    assert context.get_parameter_value("container_id") == (
        "urn:ontobdc:storage/local/imported"
    )
    assert context.get_parameter_value("container_update_completed") is None
    assert context.get_parameter_value("container_html_view_updated") is None

    dataset_graph = Graph().parse(
        dataset_path / ".__ontobdc__" / "dataset.ttl",
        format="turtle",
    )
    target_dataset = URIRef(
        "urn:ontobdc:storage/dataset/imported/documents"
    )
    assert (target_dataset, RDF.type, OBDC.EntityDataset) in dataset_graph
    assert URIRef(
        "urn:ontobdc:storage/local/imported"
    ) in dataset_graph.objects(
        target_dataset,
        OBDC.belongsToDataContainer,
    )


def test_attach_rollback_restores_original_metadata(tmp_path: Path) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()
    container_path, _ = _write_imported_container(root_path)
    context = FakeContext(root_path, container_path)
    container_file = container_path / ".__ontobdc__" / "container.ttl"
    original = container_file.read_bytes()

    inspect_container(context)
    resolve_identity(context)
    attach_container_metadata(context)
    assert container_file.read_bytes() != original

    attach_context(context)
    assert context.get_parameter_value("container_id") == (
        "urn:ontobdc:storage/local/imported"
    )

    rollback_attachment(context)

    assert container_file.read_bytes() == original
    assert context.get_parameter_value("container_id") == (
        "urn:ontobdc:storage/local/stale"
    )
    assert context.get_parameter_value("container_update_completed") is True
    assert context.get_parameter_value("container_html_view_updated") is True
