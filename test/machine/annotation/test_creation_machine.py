"""Real FSM failure boundaries, persisted observations and capability contracts."""

import json
import pytest
import ezdxf
from rdflib import Graph, Literal, RDFS, URIRef
from brasidatacenter import resources
from ontobdc.annotation.plugin.machine.annotation_creation_from_point.machine import (
    AnnotationCreationFromPointStateEvaluatorAdapter as Evaluator,
    AnnotationCreationFromPointStateTransitionHandler as Handler,
)
from ontobdc.annotation.plugin.machine.annotation_creation_from_point.state import (
    AnnotationCreationFromPointProcessState as State,
)
from ontobdc.annotation.plugin.machine.annotation_creation_from_point.etl import (
    AnnotationCreationFromPointEtlEvent as Etl,
)
from ontobdc.annotation.plugin.capability.transformation.annotation_type_identified import (
    AnnotationTypeIdentifiedCapability as Type,
)
from ontobdc.annotation.plugin.capability.transformation.annotations_created import (
    AnnotationsCreatedCapability as Create,
)
from ontobdc.annotation.plugin.capability.loader.drawable_documents_loaded import (
    DrawableDocumentsLoadedCapability,
)
from ontobdc.annotation.plugin.capability.loader.drawable_file_viewer_opened import (
    DrawableFileViewerOpenedCapability,
)
from ontobdc.annotation.plugin.capability.loader.points_captured import (
    PointsCapturedCapability,
)
from ontobdc.annotation.plugin.capability.loader.annotation_details_filled import (
    AnnotationDetailsFilledCapability,
)
from ontobdc.storage.plugin.capability.transformation.single_file_metadata_extracted import (
    SingleFileMetadataExtractedCapability as Metadata,
)
from ontobdc.shared.adapter.mime_capability import MimeCapabilityMap
from ontobdc.shared.adapter.mime_chain_capability import MimeChainExecution
from ontobdc.container.domain.exception.entity import EntityRepositoryNotInjectedError
from test.machine.annotation.support import workspace, put, MemoryRepository


@pytest.fixture
def drawing_request(tmp_path):
    disk, context = workspace(tmp_path)
    drawing = disk.container / "drawing.dxf"
    document = ezdxf.new()
    document.modelspace().add_line((0, 0), (10, 10))
    document.saveas(drawing)
    put(context, annotation_type="issue", file_open_path=str(drawing))
    return disk, context, drawing


@pytest.mark.parametrize(
    "requested,identifier",
    [
        ("issue", "issue"),
        ("alerta", "issue"),
        ("dúvida", "question"),
        (str(Type.ONTOLOGY_IRI) + "#Issue", "issue"),
    ],
)
def test_resolves_real_published_type_and_observes_matching_event(
    drawing_request, requested, identifier
):
    disk, context, drawing = drawing_request
    put(context, annotation_type=requested)
    capability = Type()
    assert not capability.is_satisfied(context)
    response = capability.execute(context)
    assert Type.identifier_of(URIRef(response["annotation_type_iri"])) == identifier
    assert capability.is_satisfied(context)
    put(context, annotation_type="note")
    assert not capability.is_satisfied(context)


def test_unknown_type_has_no_event(drawing_request):
    disk, context, drawing = drawing_request
    put(context, annotation_type="nonexistent-annotation")
    with pytest.raises(LookupError, match="No annotation type"):
        Type().execute(context)
    assert not Type.event_path(disk.root).exists()


def test_ambiguous_external_ontology_data_reports_all_matches(
    drawing_request, tmp_path, monkeypatch
):
    disk, context, drawing = drawing_request
    graph = Graph().parse(str(resources.ontology_path_for_iri(Type.ONTOLOGY_IRI)))
    types = sorted(graph.subjects(RDFS.subClassOf, Type.ANNOTATION_CLASS), key=str)
    for subject in types[:2]:
        graph.add((subject, RDFS.label, Literal("ambiguous-test")))
    catalog = tmp_path / "external-catalog"
    target = catalog / Type.ONTOLOGY_IRI.removeprefix(resources.ONTOLOGY_BASE_IRI)
    target.parent.mkdir(parents=True)
    graph.serialize(target, format="turtle")
    # Only the external resource provider is substituted, never ontobdc code.
    monkeypatch.setattr(resources, "ontology_root", lambda: catalog)
    put(context, annotation_type="ambiguous-test")
    with pytest.raises(ValueError, match="more than one") as error:
        Type().execute(context)
    assert all(str(subject) in str(error.value) for subject in types[:2])


def test_machine_performs_prerequisites_in_order_and_failure_blocks_later_states(
    drawing_request,
):
    disk, context, drawing = drawing_request
    with pytest.raises(LookupError, match="No drawable-document capability"):
        Handler(context).execute()
    etl = disk.root / ".__ontobdc__/etl/annotation/creation/point"
    events = {path.name: json.loads(path.read_text()) for path in etl.glob("*.json")}
    assert set(events) == {
        "__annotation_type_identified__.json",
        "__file_metadata_extracted__.json",
    }
    assert events["__annotation_type_identified__.json"]["result"][
        "annotation_type_iri"
    ].endswith("#Issue")
    assert events["__file_metadata_extracted__.json"]["result"]
    assert not (disk.container / "annotation").exists()


def test_resume_observes_real_outputs_backfills_empty_etl_and_never_observes_actions(
    drawing_request,
):
    disk, context, drawing = drawing_request
    Type().execute(context)
    Metadata().execute(context)
    evaluator = Evaluator()
    assert evaluator.evaluate(context) == State.FILE_METADATA_EXTRACTED
    for state in [
        State.DRAWABLE_DOCUMENTS_LOADED,
        State.DRAWABLE_FILE_VIEWER_OPENED,
        State.POINTS_CAPTURED,
        State.ANNOTATION_DETAILS_FILLED,
        State.ANNOTATIONS_CREATED,
    ]:
        Etl.write(disk.root, state, {"previous_run": True})
    assert evaluator.evaluate(context) == State.FILE_METADATA_EXTRACTED
    event = Type.event_path(disk.root)
    before = event.read_bytes()
    with pytest.raises(LookupError):
        Handler(context).execute()
    assert event.read_bytes() == before
    for state in [State.ANNOTATION_TYPE_IDENTIFIED, State.FILE_METADATA_EXTRACTED]:
        assert json.loads(Etl.path(disk.root, state).read_text())["result"] == {}


@pytest.mark.parametrize(
    "capability,message",
    [
        (DrawableDocumentsLoadedCapability, "No drawable-document capability"),
        (DrawableFileViewerOpenedCapability, "No drawable-file-viewer capability"),
        (PointsCapturedCapability, "No points-captured capability"),
        (AnnotationDetailsFilledCapability, "No annotation-details capability"),
    ],
)
def test_each_empty_mime_mapping_and_chain_fails_clearly(
    drawing_request, capability, message
):
    disk, context, drawing = drawing_request
    Metadata().execute(context)
    with pytest.raises(LookupError, match=message):
        capability().execute(context)


@pytest.mark.parametrize(
    "mapping", [[], "invalid", {"image/vnd.dxf": object}, {"image/vnd.dxf": object()}]
)
def test_invalid_mime_map_is_rejected(mapping, drawing_request):
    disk, context, drawing = drawing_request
    put(context, test_capabilities=mapping)
    with pytest.raises(TypeError):
        MimeCapabilityMap.capability_type(context, "test_capabilities", "image/vnd.dxf")


@pytest.mark.parametrize(
    "mapping,mime",
    [
        ({}, "image/vnd.dxf"),
        ({}, None),
        ({"image/vnd.dxf": Type}, None),
        ({"other": Type}, "image/vnd.dxf"),
    ],
)
def test_missing_mime_or_empty_map_cannot_select_capability(
    mapping, mime, drawing_request
):
    disk, context, drawing = drawing_request
    put(context, test_capabilities=mapping)
    assert MimeCapabilityMap.capability_type(context, "test_capabilities", mime) is None
    assert (
        MimeChainExecution._run_mime_capability(
            context, "test_capabilities", mime, ("ontobdc",)
        )
        == {}
    )


def test_annotations_created_uses_file_container_instead_of_stale_context(
    drawing_request,
):
    disk, context, drawing = drawing_request
    repository = MemoryRepository()
    put(
        context,
        entity_repository=repository,
        container_path=str(disk.root / "wrong"),
        annotation_title="Review",
        annotation_text="Body",
        captured_points=[dict(x=1, y=2)],
    )
    result = Create().execute(context)
    assert result["dataset_path"] == str(disk.container / "annotation")
    row = repository.rows(disk.container / "annotation")[result["global_id"]]
    assert row["annotation_type"] == "issue" and row["title"] == "Review"
    assert row["text"] == "Body" and row["geometry"] == "POINT(1 2)"
    assert row["source_document"] == result["source_document"]
    assert row["source_document"].endswith("/payload/document/drawing.dxf")


def test_annotations_created_requires_repository(drawing_request):
    disk, context, drawing = drawing_request
    put(context, annotation_title="Review", captured_points=[dict(x=1, y=2)])
    with pytest.raises(EntityRepositoryNotInjectedError):
        Create().execute(context)
    assert not (disk.container / "annotation").exists()


def test_etl_describes_live_objects_and_replaces_atomically(tmp_path):
    document = ezdxf.new()
    path = Etl.write(tmp_path, State.DRAWABLE_DOCUMENTS_LOADED, {"document": document})
    assert json.loads(path.read_text())["result"] == {"document": "<Drawing>"}
    Etl.write(tmp_path, State.DRAWABLE_DOCUMENTS_LOADED, {"changed": True})
    assert json.loads(path.read_text())["result"] == {"changed": True}
    assert not list(path.parent.glob("*.tmp"))


def test_registered_capability_without_annotation_title_is_rejected(drawing_request):
    disk, context, drawing = drawing_request
    Metadata().execute(context)
    from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent

    mime = OpenFileMetadataEvent.mime_for(disk.root, drawing)
    put(context, annotation_details_capability={mime: Type})
    with pytest.raises(ValueError, match="without a title"):
        AnnotationDetailsFilledCapability().execute(context)


def test_mime_dispatch_executes_the_registered_real_capability(drawing_request):
    disk, context, drawing = drawing_request
    put(context, test_capabilities={"image/vnd.dxf": Type})
    result = MimeChainExecution._run_mime_capability(
        context, "test_capabilities", "image/vnd.dxf", ("ontobdc",)
    )
    assert result[Type.METADATA.id]["annotation_type_iri"].endswith("#Issue")
    assert Type().is_satisfied(context)


def test_missing_mime_metadata_must_not_block_before_responsibility_lookup(
    drawing_request,
):
    disk, context, drawing = drawing_request
    unknown = drawing.with_suffix(".dwg")
    drawing.rename(unknown)
    put(context, file_open_path=str(unknown))
    with pytest.raises(LookupError, match="MIME type"):
        Handler(context).execute()


def test_initial_undefined_state_has_its_own_etl_event(drawing_request):
    disk, context, drawing = drawing_request
    with pytest.raises(LookupError):
        Handler(context).execute()
    assert Etl.path(disk.root, State.UNDEFINED).is_file()
