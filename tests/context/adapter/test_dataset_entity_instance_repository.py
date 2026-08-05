import json
from pathlib import Path

import pytest

from ontobdc.context.adapter.instance import DatasetEntityInstanceRepository


WORK_STREAM_URI = "https://example.org/ontology#WorkStream"
RISK_URI = "https://example.org/ontology#Risk"


def _write_dataset_metadata(
    dataset_path: Path,
    *,
    dataset_uri: str,
    data_entity_uris: list[str],
) -> None:
    metadata_path = dataset_path / ".__ontobdc__" / "dataset.ttl"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    entity_statements = " ;\n        obdc:hasDataEntity ".join(
        f"<{entity_uri}>" for entity_uri in data_entity_uris
    )
    metadata_path.write_text(
        "\n".join(
            [
                "@prefix obdc: <http://ontobdc.org/ontology/domain/ns.ttl#> .",
                "",
                f"<{dataset_uri}> a obdc:EntityDataset ;",
                f"    obdc:hasDataEntity {entity_statements} .",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_datapackage(dataset_path: Path, resources: list[dict]) -> None:
    datapackage_path = dataset_path / ".__ontobdc__" / "datapackage.json"
    datapackage_path.parent.mkdir(parents=True, exist_ok=True)
    datapackage_path.write_text(
        json.dumps(
            {
                "name": "multi_entity_dataset",
                "resources": resources,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _csv_resource(
    *,
    name: str,
    path: str,
    entity_uri: str,
    entity_identifier: str,
) -> dict:
    return {
        "name": name,
        "path": path,
        "format": "csv",
        "schema": {
            "fields": [
                {"name": "GlobalId", "type": "string"},
                {"name": "Name", "type": "string"},
            ],
            "primaryKey": ["GlobalId"],
        },
        "entityUri": entity_uri,
        "entityIdentifier": entity_identifier,
    }


def test_lists_only_resources_declared_for_requested_entity(
    tmp_path: Path,
) -> None:
    pytest.importorskip("frictionless")
    dataset_path = tmp_path / ".planning"
    _write_dataset_metadata(
        dataset_path,
        dataset_uri="urn:dataset:planning",
        data_entity_uris=["urn:instance:ws-1", "urn:instance:risk-1"],
    )
    _write_csv(
        dataset_path / "payload" / "data" / "anything.csv",
        "GlobalId,Name\nws-1,Cabeamento\n",
    )
    _write_csv(
        dataset_path / "payload" / "data" / "other.csv",
        "GlobalId,Name\nrisk-1,Atraso\n",
    )
    _write_datapackage(
        dataset_path,
        resources=[
            _csv_resource(
                name="arbitrary_work_stream_resource",
                path="../payload/data/anything.csv",
                entity_uri=WORK_STREAM_URI,
                entity_identifier="work_stream",
            ),
            _csv_resource(
                name="arbitrary_risk_resource",
                path="../payload/data/other.csv",
                entity_uri=RISK_URI,
                entity_identifier="risk",
            ),
        ],
    )

    payload = DatasetEntityInstanceRepository(
        dataset_path=str(dataset_path),
        entity="WorkStream",
    ).list_instances()

    assert payload["resolution"] == "dataset_datapackage"
    assert payload["entity_uri"] == WORK_STREAM_URI
    assert payload["resource_count"] == 1
    assert payload["instance_count"] == 1
    assert payload["instances"] == [
        {
            "GlobalId": "ws-1",
            "Name": "Cabeamento",
        }
    ]


def test_aggregates_multiple_resources_for_same_entity(tmp_path: Path) -> None:
    pytest.importorskip("frictionless")
    dataset_path = tmp_path / ".planning"
    _write_dataset_metadata(
        dataset_path,
        dataset_uri="urn:dataset:planning",
        data_entity_uris=["urn:instance:ws-1", "urn:instance:ws-2"],
    )
    _write_csv(
        dataset_path / "payload" / "data" / "first.csv",
        "GlobalId,Name\nws-1,Cabeamento\n",
    )
    _write_csv(
        dataset_path / "payload" / "data" / "second.csv",
        "GlobalId,Name\nws-2,CFTV\n",
    )
    _write_datapackage(
        dataset_path,
        resources=[
            _csv_resource(
                name="first_part",
                path="../payload/data/first.csv",
                entity_uri=WORK_STREAM_URI,
                entity_identifier="work_stream",
            ),
            _csv_resource(
                name="second_part",
                path="../payload/data/second.csv",
                entity_uri=WORK_STREAM_URI,
                entity_identifier="work_stream",
            ),
        ],
    )

    payload = DatasetEntityInstanceRepository(
        dataset_path=str(dataset_path),
        entity="work_stream",
    ).list_instances()

    assert payload["resource_count"] == 2
    assert payload["instance_count"] == 2
    assert [instance["GlobalId"] for instance in payload["instances"]] == [
        "ws-1",
        "ws-2",
    ]


def test_rejects_entity_without_datapackage_resource(tmp_path: Path) -> None:
    dataset_path = tmp_path / ".planning"
    _write_dataset_metadata(
        dataset_path,
        dataset_uri="urn:dataset:planning",
        data_entity_uris=["urn:instance:risk-1"],
    )
    _write_datapackage(
        dataset_path,
        resources=[
            _csv_resource(
                name="risk_resource",
                path="../payload/data/risk.csv",
                entity_uri=RISK_URI,
                entity_identifier="risk",
            )
        ],
    )

    repository = DatasetEntityInstanceRepository(
        dataset_path=str(dataset_path),
        entity="WorkStream",
    )

    assert repository.contains_entity() is False
    with pytest.raises(ValueError, match="does not expose a resource"):
        repository.list_instances()
