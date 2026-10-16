from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from rdflib import XSD

import ontobdc.cli
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.plugin.command.create import AnnotationCreateCommand
from ontobdc.annotate.plugin.command.update import AnnotationUpdateCommand
from ontobdc.annotate.plugin.command.clear import AnnotationClearCommand
from ontobdc.annotate.plugin.command.list import AnnotationListCommand
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.annotate.adapter.excel_workbook import AnnotationWorkbook, ExportedItem
from test.machine.annotate.support import workspace, put, MemoryRepository


def test_completion_roundtrip_preserves_timezone_and_legacy_rows():
    annotation = Annotation(annotation_type="issue", title="Review", completed_at="2026-10-15T10:30:00-03:00")
    assert annotation.to_record()["completed_at"] == "2026-10-15T10:30:00-03:00"
    assert Annotation.from_record(annotation.to_record()).completed_at == annotation.completed_at
    row = annotation.to_record()
    row.pop("completed_at")
    assert Annotation.from_record(row).completed_at is None
    row["completed_at"] = ""
    assert Annotation.from_record(row).completed_at is None
    assert "completed_at" not in Annotation(annotation_type="note", title="Open").to_record()


def test_completion_rejects_invalid_dates():
    with pytest.raises(ValidationError):
        Annotation(annotation_type="issue", title="Review", completed_at="not-a-date")


def test_facade_exposes_optional_datetime_with_localized_labels():
    facade = EntityFacadeLocator.of(Annotation.ENTITY_IRI)
    field = next(field for field in facade.fields if field.identifier == "completed_at")
    assert field.datatype == str(XSD.dateTime)
    assert not field.required and not field.multivalued
    assert field.labels["pt-br"] == "Data de conclusão"
    assert field.maps_to_resource == Annotation.ENTITY_IRI.rsplit("#", 1)[0] + "#completedAt"
    assert len({field.order for field in facade.fields}) == len(facade.fields)


def test_create_update_clear_and_list_completion(tmp_path):
    disk, context = workspace(tmp_path)
    repository = MemoryRepository()
    put(context, entity_repository=repository, container_path=str(disk.container),
        annotation_title="Review", annotation_completed_at="2026-10-15T10:30:00-03:00")
    create = AnnotationCreateCommand(SimpleNamespace(context=context,
        command_args=["--title", "Review", "--completed-at", "2026-10-15T10:30:00-03:00"]))
    assert create.check()
    result = create.run()
    guid = result.content["global_id"]
    put(context, container_path=str(disk.container), annotation_guid=guid, annotation_completed_at="2026-10-16T12:00:00-03:00")
    update = AnnotationUpdateCommand(SimpleNamespace(context=context,
        command_args=["--guid", guid, "--completed-at", "2026-10-16T12:00:00-03:00"]))
    assert update.check()
    update.run()
    put(context, container_path=str(disk.container))
    listing = AnnotationListCommand(SimpleNamespace(context=context, command_args=["--list"]))
    items = [item for group in listing.run().content["groups"] for item in group["annotations"]]
    assert items[0]["completed_at"] == "2026-10-16T12:00:00-03:00"
    clear = AnnotationClearCommand(SimpleNamespace(context=context,
        command_args=["--guid", guid, "--clear", "completed_at"]))
    assert clear.check()
    clear.run()
    put(context, container_path=str(disk.container))
    items = [item for group in listing.run().content["groups"] for item in group["annotations"]]
    assert items[0]["completed_at"] == ""


def test_excel_export_includes_completion_date():
    workbook = AnnotationWorkbook("Project", "Issues", [ExportedItem(
        item="01", global_id="one", title="Review", text="", author="",
        created_at="2026-10-14T09:00:00", completed_at="2026-10-15T10:30:00-03:00",
    )], [], language="pt-br").build()
    sheet = workbook[AnnotationWorkbook.INDEX_SHEET]
    assert sheet["J7"].value == "Data de conclusão"
    assert sheet["J8"].value == datetime(2026, 10, 15, 10, 30)
