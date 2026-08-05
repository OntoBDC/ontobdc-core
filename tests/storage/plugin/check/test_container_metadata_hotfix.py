from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from ontobdc.storage.plugin.check.is_container_metadata_ready import hotfix


OBDC = Namespace("http://ontobdc.org/ontology/domain/ns.ttl#")
CT = Namespace(
    "http://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
)


def test_hotfix_repairs_identity_without_renaming_container(
    tmp_path: Path,
) -> None:
    root_path = tmp_path / "my-desktop"
    container_path = root_path / "techcenter-doc"
    metadata_path = container_path / ".__ontobdc__" / "container.ttl"
    metadata_path.parent.mkdir(parents=True)

    source_container = URIRef("urn:ontobdc:storage/local/old-root/labsea")
    dataset = URIRef("urn:ontobdc:storage/dataset/labsea/documents")
    title = Literal(
        "Real Estate Brazil (Official)-Obras - Exp LabSea2025",
        lang="en",
    )
    description = Literal("LabSea project container", lang="en")
    created = Literal(
        datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
        datatype=XSD.dateTime,
    )

    graph = Graph()
    graph.add((source_container, RDF.type, OBDC.DataContainer))
    graph.add(
        (
            source_container,
            DCTERMS.identifier,
            Literal(str(source_container)),
        )
    )
    graph.add((source_container, DCTERMS.title, title))
    graph.add((source_container, CT.description, description))
    graph.add((source_container, CT.creationDate, created))
    graph.add(
        (
            source_container,
            PROV.atLocation,
            URIRef("file:///old-root/labsea"),
        )
    )
    graph.add((source_container, OBDC.hasEntityDataset, dataset))
    graph.add((dataset, OBDC.belongsToDataContainer, source_container))
    graph.serialize(metadata_path, format="turtle")

    assert hotfix.main(str(container_path), str(root_path)) == 0

    repaired = Graph().parse(metadata_path, format="turtle")
    target_container = URIRef(
        "urn:ontobdc:storage/local/techcenter-doc"
    )

    assert (target_container, RDF.type, OBDC.DataContainer) in repaired
    assert list(repaired.objects(target_container, DCTERMS.title)) == [title]
    assert list(repaired.objects(target_container, CT.description)) == [
        description
    ]
    assert list(repaired.objects(target_container, CT.creationDate)) == [
        created
    ]
    assert (
        target_container,
        PROV.atLocation,
        URIRef(container_path.resolve().as_uri()),
    ) in repaired
    assert (target_container, OBDC.hasEntityDataset, dataset) in repaired
    assert (dataset, OBDC.belongsToDataContainer, target_container) in repaired
    assert not any(repaired.predicate_objects(source_container))
