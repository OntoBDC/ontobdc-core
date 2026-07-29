import json

import pytest

from ontobdc.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookField,
)


def test_generates_entity_workbook_and_datapackage(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")

    artifact = EntityWorkbookAdapter().generate(
        output_dir=tmp_path / "payload" / "document",
        workbook_name="workstreams.xlsx",
        worksheet_name="WorkStream",
        fields=[
            EntityWorkbookField("GlobalId"),
            EntityWorkbookField("Description"),
            EntityWorkbookField("Name"),
        ],
        records=[
            {
                "GlobalId": "workstream-1",
                "Description": "",
                "Name": "Cabeamento de Lógica e Instrumentação",
            }
        ],
        datapackage_path=tmp_path / ".__ontobdc__" / "datapackage.json",
        package_name="ontobdc_container",
        resource_name="work_stream",
        primary_key=["GlobalId"],
    )

    workbook = openpyxl.load_workbook(artifact.workbook_path)
    worksheet = workbook["WorkStream"]
    assert [cell.value for cell in worksheet[1]] == [
        "GlobalId",
        "Description",
        "Name",
    ]
    assert worksheet["C2"].value == "Cabeamento de Lógica e Instrumentação"
    workbook.close()

    descriptor = json.loads(
        artifact.datapackage_path.read_text(encoding="utf-8")
    )
    resource = next(
        item
        for item in descriptor["resources"]
        if item["name"] == "work_stream"
    )
    assert resource["path"] == "../payload/document/workstreams.xlsx"
    assert resource["dialect"]["excel"]["sheet"] == "WorkStream"
    assert artifact.validation["valid"] is True


def test_preserves_other_datapackage_resources(tmp_path) -> None:
    pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")
    datapackage_path = tmp_path / ".__ontobdc__" / "datapackage.json"
    datapackage_path.parent.mkdir(parents=True)
    datapackage_path.write_text(
        json.dumps(
            {
                "name": "existing_container",
                "resources": [
                    {
                        "name": "existing",
                        "path": "../payload/existing.csv",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    EntityWorkbookAdapter().generate(
        output_dir=tmp_path / "payload" / "document",
        workbook_name="workstreams.xlsx",
        worksheet_name="WorkStream",
        fields=[EntityWorkbookField("GlobalId")],
        records=[{"GlobalId": "workstream-1"}],
        datapackage_path=datapackage_path,
        package_name="ontobdc_container",
        resource_name="work_stream",
        primary_key=["GlobalId"],
    )

    descriptor = json.loads(datapackage_path.read_text(encoding="utf-8"))
    assert descriptor["name"] == "existing_container"
    assert [item["name"] for item in descriptor["resources"]] == [
        "existing",
        "work_stream",
    ]
