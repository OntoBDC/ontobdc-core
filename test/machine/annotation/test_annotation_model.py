"""Annotation validation and persistence contracts, including known precision loss."""

import re
import pytest
from pydantic import ValidationError
from ontobdc.annotation.domain.model.annotation import Annotation
from test.machine.annotation.support import MemoryRepository, workspace, put


def annotation(**changes):
    values = dict(
        global_id="a",
        annotation_type="note",
        title="Review",
        points=[dict(x=1.5, y=2)],
        source_document="urn:drawing",
    )
    values.update(changes)
    return Annotation(**values)


@pytest.mark.parametrize("field", ["title", "annotation_type", "source_document"])
@pytest.mark.parametrize("blank", ["", " \t\n"])
def test_rejects_blank_required_fields(field, blank):
    with pytest.raises(ValidationError):
        annotation(**{field: blank})


def test_rejects_empty_point_sequence():
    with pytest.raises(ValidationError):
        annotation(points=[])


@pytest.mark.parametrize(
    "points,wkt",
    [
        ([dict(x=1.5, y=3)], "POINT(1.5 3)"),
        (
            [dict(x=-0.25, y=1e-7), dict(x=3, y=4), dict(x=0, y=-2)],
            "LINESTRING(-0.25 1e-07, 3 4, 0 -2)",
        ),
    ],
)
def test_geometry_preserves_order_and_numeric_forms(points, wkt):
    assert annotation(points=points).geometry == wkt


def test_geometry_preserves_cad_coordinate_precision():
    model = annotation(points=[dict(x=7500123.456, y=1234567.891)])
    numbers = [
        float(value)
        for value in re.findall(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", model.geometry)
    ]
    assert numbers == pytest.approx([7500123.456, 1234567.891], abs=1e-6, rel=0)


def test_record_omits_only_missing_optional_values():
    model = annotation(title="  Review  ")
    record = model.to_record()
    assert record["title"] == "Review"
    assert record["global_id"] == "a"
    assert record["geometry"] == "POINT(1.5 2)"
    assert "text" not in record and "author" not in record
    assert annotation(text="Body", author="Elias").to_record()["text"] == "Body"


@pytest.mark.parametrize(
    "key",
    [
        "container_path",
        "dataset_path",
        "dataset_entity_iri",
        "entity_records",
        "entity_source_documents",
    ],
)
def test_save_restores_callers_existing_context_parameters(tmp_path, key):
    disk, context = workspace(tmp_path)
    repository = MemoryRepository()
    original = "previous caller value"
    put(context, entity_repository=repository, **{key: original})
    annotation().save(context, str(disk.container))
    assert context.get_parameter_value(key) == original


def test_save_does_not_leak_dataset_title_into_caller_context(tmp_path):
    disk, context = workspace(tmp_path)
    put(context, entity_repository=MemoryRepository())
    annotation().save(context, str(disk.container))
    assert not context.has_parameter("dataset_title")


def test_nonisolated_save_must_not_persist_internal_dataset_title(tmp_path):
    from ontobdc.cli.adapter.context import CliContextAdapter

    disk, _ = workspace(tmp_path)
    context = CliContextAdapter([], root_dir=str(disk.root))
    put(context, entity_repository=MemoryRepository())
    annotation().save(context, str(disk.container))
    restored = CliContextAdapter([], root_dir=str(disk.root))
    assert not restored.has_parameter("dataset_title")


def test_isolated_save_keeps_persistent_context_file_unchanged(tmp_path):
    from ontobdc.cli.adapter.context import CliContextAdapter, IsolatedCliContextAdapter

    disk, _ = workspace(tmp_path)
    persistent = CliContextAdapter([], root_dir=str(disk.root))
    put(persistent, caller_marker="preserve")
    path = disk.root / ".__ontobdc__/context.ttl"
    before = path.read_bytes()
    context = IsolatedCliContextAdapter([], root_dir=str(disk.root))
    put(context, entity_repository=MemoryRepository())
    annotation().save(context, str(disk.container))
    assert path.read_bytes() == before
    assert (
        CliContextAdapter([], root_dir=str(disk.root)).get_parameter_value(
            "caller_marker"
        )
        == "preserve"
    )


def test_same_global_id_save_replaces_row_with_full_facade_values(tmp_path):
    disk, context = workspace(tmp_path)
    repository = MemoryRepository()
    put(context, entity_repository=repository)
    annotation(text="Remove this").save(context, str(disk.container))
    annotation(title="Changed title").save(context, str(disk.container))
    rows = repository.rows(disk.container / "annotation")
    assert len(rows) == 1
    assert rows["a"]["title"] == "Changed title" and rows["a"]["text"] == ""
