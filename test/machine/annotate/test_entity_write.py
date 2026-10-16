"""Repository-port integration with real dataset creation, facade and linkset."""

import pytest
from rdflib import Graph, RDF
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.container.plugin.machine.entity_write.machine import (
    EntityWriteStateTransitionHandler as Handler,
    EntityWriteStateEvaluatorAdapter as Evaluator,
)
from ontobdc.container.plugin.machine.entity_write.state import (
    EntityWriteProcessState as State,
)
from ontobdc.container.domain.exception.entity import (
    EntityRepositoryNotInjectedError,
    EntityFacadeNotFoundError,
)
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_linkset import EntityLinkset
from ontobdc.shared.domain.vocabulary import ICDD_CONTAINER, ICDD_LINKSET, CT
from test.machine.annotate.support import workspace, put, MemoryRepository
from test.machine.annotate.test_annotation_model import annotation


@pytest.fixture
def write_request(tmp_path):
    disk, context = workspace(tmp_path)
    repo = MemoryRepository()
    put(
        context,
        container_path=str(disk.container),
        dataset_entity_iri=Annotation.ENTITY_IRI,
        entity_repository=repo,
        entity_records=[annotation().to_record()],
        entity_source_documents=["urn:plan-a"],
    )
    return disk, context, repo


def test_first_write_observes_each_persistent_state_and_is_idempotent(write_request):
    disk, context, repo = write_request
    assert Evaluator().evaluate(context) == State.UNDEFINED
    handler = Handler(context)
    for state in [
        State.DATASET_FOUND,
        State.DATA_SOURCE_AVAILABLE,
        State.DATA_SOURCE_COLUMNS_SYNCED,
        State.DATA_SOURCE_FILLED,
        State.ENTITY_DOCUMENTS_LINKED,
    ]:
        handler.perform_state_transition(state)
        assert Evaluator().evaluate(context) == state
    dataset = disk.container / "annotation"
    assert repo.rows(dataset)["a"]["title"] == "Review"
    before = {p: p.read_bytes() for p in dataset.rglob("*") if p.is_file()}
    writes = repo.writes
    Handler(context).execute()
    assert repo.writes == writes
    assert {p: p.read_bytes() for p in dataset.rglob("*") if p.is_file()} == before


def test_resume_only_fills_missing_columns_rows_and_links(write_request):
    disk, context, repo = write_request
    handler = Handler(context)
    handler.perform_state_transition(State.DATASET_FOUND)
    handler.perform_state_transition(State.DATA_SOURCE_AVAILABLE)
    assert repo.columns(disk.container / "annotation") == ["global_id"]
    Handler(context).execute()
    assert Evaluator().evaluate(context) == State.ENTITY_DOCUMENTS_LINKED
    assert len(repo.columns(disk.container / "annotation")) == 8
    assert repo.writes == 1


def test_changed_content_replaces_existing_row_and_removed_text_becomes_empty(
    write_request,
):
    disk, context, repo = write_request
    put(context, entity_records=[annotation(text="Old body").to_record()])
    Handler(context).execute()
    put(context, entity_records=[annotation(title="Changed").to_record()])
    assert Evaluator().evaluate(context) == State.DATA_SOURCE_COLUMNS_SYNCED
    Handler(context).execute()
    rows = repo.rows(disk.container / "annotation")
    assert len(rows) == 1
    assert rows["a"]["title"] == "Changed" and rows["a"]["text"] == ""


@pytest.mark.parametrize(
    "changes",
    [{"unknown": "x"}, {"title": None}, {"source_document": None}, {"global_id": None}],
)
def test_invalid_row_fails_before_repository_writes_and_blocks_links(
    write_request, changes
):
    disk, context, repo = write_request
    row = annotation().to_record()
    row.update(changes)
    put(context, entity_records=[row])
    with pytest.raises(ValueError):
        Handler(context).execute()
    assert repo.writes == 0
    assert not list((disk.container / "annotation/payload/linkset").glob("*.ttl"))


def test_directory_collision_is_not_silently_adopted(write_request):
    disk, context, repo = write_request
    (disk.container / "annotation").mkdir()
    with pytest.raises(FileExistsError, match="not a dataset"):
        Handler(context).execute()
    assert repo.writes == 0


def test_missing_facade_fails_with_original_exception(write_request):
    disk, context, repo = write_request
    put(context, dataset_entity_iri="urn:unpublished-entity")
    with pytest.raises(EntityFacadeNotFoundError):
        Handler(context).execute()
    assert repo.writes == 0


def test_repository_is_required_at_handler_construction(tmp_path):
    disk, context = workspace(tmp_path)
    with pytest.raises(EntityRepositoryNotInjectedError):
        Handler(context)


def test_linkset_unions_sources_and_retains_previous_document_after_replacement(
    write_request,
):
    disk, context, repo = write_request
    Handler(context).execute()
    put(
        context,
        entity_records=[
            annotation(title="Moved", source_document="urn:plan-b").to_record()
        ],
        entity_source_documents=["urn:plan-b"],
    )
    Handler(context).execute()
    dataset = disk.container / "annotation"
    linkset = EntityLinkset(dataset, repo.data_source_path(dataset))
    assert linkset.links() == ["urn:plan-a", "urn:plan-b"]
    graph = Graph().parse(linkset.path)
    assert (
        linkset.data_source_document,
        RDF.type,
        ICDD_CONTAINER.InternalDocument,
    ) in graph
    assert len(set(graph.subjects(RDF.type, ICDD_LINKSET.DirectedBinaryLink))) == 2
    assert str(ICDD_CONTAINER).startswith("https:") and str(CT).startswith("http:")
    assert len(repo.rows(dataset)) == 1


def test_undefined_transition_validation_does_not_hide_action_error(write_request):
    disk, context, repo = write_request
    handler = Handler(context)
    assert (
        handler.validate_state_transition(State.UNDEFINED, State.DATASET_FOUND) is False
    )
    (disk.container / "annotation").mkdir()
    with pytest.raises(FileExistsError):
        handler.execute()


def test_real_facade_has_ten_columns_in_published_order():
    facade = EntityFacadeLocator.of(Annotation.ENTITY_IRI)
    assert facade.column_names() == [
        "global_id",
        "annotation_type",
        "title",
        "text",
        "geometry",
        "source_document",
        "author",
        "created_at",
        "completed_at",
        "related_documents",
    ]
    assert [field.identifier for field in facade.fields if field.required] == [
        "global_id",
        "annotation_type",
        "title",
        "created_at",
    ]
    assert [field.order for field in facade.fields] == sorted(
        {field.order for field in facade.fields}
    )
