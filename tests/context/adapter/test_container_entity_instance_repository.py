import json
from pathlib import Path

import pytest

from ontobdc.context.adapter.instance import ContainerEntityInstanceRepository


WORK_STREAM_URI = "https://example.org/ontology#WorkStream"
RISK_URI = "https://example.org/ontology#Risk"


def _write_dataset(
    dataset_path: Path,
    *,
    dataset_uri: str,
    global_id: str,
    name: str,
) -> None:
    metadata_dir = dataset_path / ".__ontobdc__"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "dataset.ttl").write_text(
        "\n".join(
            [
                "@prefix obdc: <http://ontobdc.org/ontology/domain/ns.ttl#> .",
                "",
                f"<{dataset_uri}> a obdc:EntityDataset ;",
                f"    obdc:hasDataEntity <urn:instance:{global_id}>,",
                f"        <urn:risk-instance:{global_id}> .",
                "",
            ]
        ),
        encoding="utf-8",
    )

    csv_path = dataset_path / "payload" / "data" / f"{global_id}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        f"GlobalId,Name,Secret\n{global_id},{name},internal\n",
        encoding="utf-8",
    )
    (metadata_dir / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "dataset",
                "resources": [
                    {
                        "name": f"resource_{global_id}",
                        "path": f"../payload/data/{global_id}.csv",
                        "format": "csv",
                        "schema": {
                            "fields": [
                                {"name": "GlobalId", "type": "string"},
                                {"name": "Name", "type": "string"},
                                {"name": "Secret", "type": "string"},
                            ],
                            "primaryKey": ["GlobalId"],
                        },
                        "entityUri": WORK_STREAM_URI,
                        "entityIdentifier": "work_stream",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_facade(metadata_dir / "linkset" / "facade.ttl")


def _write_facade(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "@prefix f: <https://example.org/facade#> .",
                "@prefix schema: <https://schema.org/> .",
                "@prefix type: <https://example.org/ontology#> .",
                "",
                "type:WorkStream f:hasDataEntityFacade f:WorkStreamFacade .",
                "type:Risk f:hasDataEntityFacade f:RiskFacade .",
                "",
                "f:WorkStreamFacade f:hasFacadeField",
                "    f:WorkStreamGlobalIdField,",
                "    f:WorkStreamNameField .",
                "",
                "f:RiskFacade f:hasFacadeField f:RiskNameField .",
                "",
                "f:WorkStreamGlobalIdField",
                "    schema:identifier \"global_id\" .",
                "",
                "f:WorkStreamNameField",
                "    schema:identifier \"name\" .",
                "",
                "f:RiskNameField",
                "    schema:identifier \"name\" .",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_container(container_path: Path, datasets: list[tuple[str, Path]]) -> None:
    metadata_dir = container_path / ".__ontobdc__"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    dataset_links = ",\n        ".join(
        f"<{dataset_uri}>" for dataset_uri, _ in datasets
    )
    dataset_descriptions = "\n\n".join(
        "\n".join(
            [
                f"<{dataset_uri}> a obdc:EntityDataset ;",
                f"    prov:atLocation <{dataset_path.as_uri()}> .",
            ]
        )
        for dataset_uri, dataset_path in datasets
    )
    (metadata_dir / "container.ttl").write_text(
        "\n".join(
            [
                "@prefix obdc: <http://ontobdc.org/ontology/domain/ns.ttl#> .",
                "@prefix prov: <http://www.w3.org/ns/prov#> .",
                "",
                "<urn:container:test> a obdc:DataContainer ;",
                f"    obdc:hasEntityDataset {dataset_links} .",
                "",
                dataset_descriptions,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_lists_dataset_instances_through_shared_dataset_facades(
    tmp_path: Path,
) -> None:
    pytest.importorskip("frictionless")
    container_path = tmp_path / "container"
    first_dataset = container_path / ".first"
    second_dataset = container_path / ".second"
    _write_dataset(
        first_dataset,
        dataset_uri="urn:dataset:first",
        global_id="ws-1",
        name="Cabeamento",
    )
    _write_dataset(
        second_dataset,
        dataset_uri="urn:dataset:second",
        global_id="ws-2",
        name="CFTV",
    )
    _write_container(
        container_path,
        datasets=[
            ("urn:dataset:first", first_dataset),
            ("urn:dataset:second", second_dataset),
        ],
    )

    # The container reader must not use a root datapackage.
    (container_path / ".__ontobdc__" / "datapackage.json").write_text(
        "{invalid json",
        encoding="utf-8",
    )

    payload = ContainerEntityInstanceRepository(
        container_path=str(container_path),
        entity="WorkStream",
    ).list_instances()

    assert payload["resolution"] == "container_dataset_facade"
    assert payload["entity_uri"] == WORK_STREAM_URI
    assert payload["dataset_count"] == 2
    assert payload["instance_count"] == 2
    assert payload["instances"] == [
        {"GlobalId": "ws-1", "Name": "Cabeamento"},
        {"GlobalId": "ws-2", "Name": "CFTV"},
    ]
    assert all(
        "Secret" not in instance for instance in payload["instances"]
    )


def test_returns_no_instances_when_no_dataset_declares_entity(
    tmp_path: Path,
) -> None:
    container_path = tmp_path / "container"
    dataset_path = container_path / ".risk"
    metadata_dir = dataset_path / ".__ontobdc__"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "dataset.ttl").write_text(
        "\n".join(
            [
                "@prefix obdc: <http://ontobdc.org/ontology/domain/ns.ttl#> .",
                "<urn:dataset:risk> a obdc:EntityDataset ;",
                "    obdc:hasDataEntity <urn:instance:risk-1> .",
            ]
        ),
        encoding="utf-8",
    )
    facade_path = metadata_dir / "linkset" / "facade.ttl"
    facade_path.parent.mkdir(parents=True, exist_ok=True)
    facade_path.write_text(
        "\n".join(
            [
                "@prefix f: <https://example.org/facade#> .",
                "@prefix schema: <https://schema.org/> .",
                "@prefix type: <https://example.org/ontology#> .",
                "type:Risk f:hasDataEntityFacade f:RiskFacade .",
                "f:RiskFacade f:hasFacadeField f:RiskNameField .",
                "f:RiskNameField schema:identifier \"name\" .",
            ]
        ),
        encoding="utf-8",
    )
    _write_container(
        container_path,
        datasets=[("urn:dataset:risk", dataset_path)],
    )

    payload = ContainerEntityInstanceRepository(
        container_path=str(container_path),
        entity="WorkStream",
    ).list_instances()

    assert payload["dataset_count"] == 0
    assert payload["instance_count"] == 0
    assert payload["instances"] == []
