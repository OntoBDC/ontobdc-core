"""Dataset creation contracts and percent-encoded document identity."""

import pytest
from rdflib import Graph, URIRef, RDF, DCTERMS
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.container.plugin.machine.dataset_create.machine import (
    DatasetCreateStateTransitionHandler as Handler,
    DatasetCreateStateEvaluatorAdapter as Evaluator,
)
from ontobdc.container.plugin.machine.dataset_create.state import (
    DatasetCreateProcessState as State,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.check import main as check
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from test.machine.annotate.support import workspace, put


def test_dataset_states_typing_title_and_idempotence(tmp_path):
    disk, context = workspace(tmp_path)
    dataset = disk.container / "custom"
    put(
        context,
        dataset_path=str(dataset),
        dataset_entity_iri=Annotation.ENTITY_IRI,
        dataset_title="Review drawings",
    )
    assert Evaluator().evaluate(context) == State.UNDEFINED
    handler = Handler(context)
    for state in [
        State.DIRECTORY_READY,
        State.DATASET_METADATA_READY,
        State.DATASET_CONTAINER_INDEX_READY,
    ]:
        handler.perform_state_transition(state)
        assert Evaluator().evaluate(context) == state
    metadata = StorageBootstrap.get_dataset_storage_file_path(dataset)
    graph = Graph().parse(metadata)
    assert list(graph.subjects(RDF.type, URIRef(Annotation.ENTITY_IRI)))
    assert "Review drawings" in {
        str(value) for value in graph.objects(None, DCTERMS.title)
    }
    before = {p: p.read_bytes() for p in disk.root.rglob("*") if p.is_file()}
    Handler(context).execute()
    assert {p: p.read_bytes() for p in disk.root.rglob("*") if p.is_file()} == before
    assert check(root_path=str(disk.root), dataset_path=str(dataset)) == 0
    assert (
        check(
            root_path=str(disk.root),
            dataset_path=str(dataset),
            entity_iri=Annotation.ENTITY_IRI,
        )
        == 0
    )
    assert (
        check(
            root_path=str(disk.root), dataset_path=str(dataset), entity_iri="urn:wrong"
        )
        != 0
    )


def test_file_target_is_invalid_and_never_overwritten(tmp_path):
    disk, context = workspace(tmp_path)
    path = disk.container / "file"
    path.write_text("preserve")
    put(context, dataset_path=str(path))
    result = Handler(context).execute()
    assert result.content["current_state"] == State.INVALID_PATH.value
    assert path.read_text() == "preserve"


def test_document_iri_encodes_identifier_accents_spaces_but_preserves_directory_separator(
    tmp_path,
):
    disk, context = workspace(tmp_path)
    drawing = disk.container / "Pavimento 1" / "Revisão elétrica.dxf"
    drawing.parent.mkdir()
    drawing.touch()
    iri = str(ContainerDocumentIri.of(disk.container, drawing))
    assert (
        iri
        == "urn:ontobdc:storage/container/"
        + disk.identifier.replace(":", "%3A")
        + "/payload/document/Pavimento%201/Revis%C3%A3o%20el%C3%A9trica.dxf"
    )
    assert ContainerDocumentIri.container_of(drawing) == disk.container
    with pytest.raises(ValueError, match="not inside"):
        ContainerDocumentIri.of(disk.container, tmp_path / "outside.dxf")
    with pytest.raises(LookupError, match="not inside any container"):
        ContainerDocumentIri.container_of(tmp_path / "outside.dxf")


def test_dataset_without_entity_type_accepts_general_check_only(tmp_path):
    disk, context = workspace(tmp_path)
    dataset = disk.container / "untyped"
    put(context, dataset_path=str(dataset))
    Handler(context).execute()
    assert check(root_path=str(disk.root), dataset_path=str(dataset)) == 0
    assert (
        check(
            root_path=str(disk.root),
            dataset_path=str(dataset),
            entity_iri=Annotation.ENTITY_IRI,
        )
        != 0
    )
