import csv

import ontobdc.cli
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_listing import ContainerEntities


ENTITY = "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation"


def test_legacy_csv_lists_all_facade_fields_and_excludes_undeclared_columns(tmp_path):
    directory = tmp_path / "payload" / "document"
    directory.mkdir(parents=True)
    with (directory / "annotations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["global_id", "title", "internal_column"])
        writer.writeheader()
        writer.writerow({"global_id": "one", "title": "Review", "internal_column": "hidden"})
    facade = EntityFacadeLocator.of(ENTITY)
    entities = ContainerEntities._csv_entities(tmp_path, "Annotation", facade)
    fields = entities[0]["fields"]
    assert [field["name"] for field in fields] == facade.column_names()
    by_name = {field["name"]: field for field in fields}
    assert by_name["title"]["values"] == ["Review"]
    assert by_name["completed_at"]["values"] == []
    assert by_name["completed_at"]["labels"]["pt-br"] == "Data de conclusão"
    assert "internal_column" not in by_name


def test_empty_row_still_exposes_every_declared_field():
    facade = EntityFacadeLocator.of(ENTITY)
    fields = ContainerEntities._csv_fields({}, facade)
    assert [field["name"] for field in fields] == facade.column_names()
    assert all(field["values"] == [] for field in fields)


def test_no_facade_does_not_expose_raw_csv_columns():
    assert ContainerEntities._csv_fields({"title": "Review", "internal": "hidden"}, None) == []
