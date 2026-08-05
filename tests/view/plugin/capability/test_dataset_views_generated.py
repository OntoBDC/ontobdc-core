import json
from pathlib import Path
from typing import Any, Dict

import pytest

from ontobdc.view.domain.machine.state import ContainerViewProcessState
from ontobdc.view.plugin.capability.dataset_views_generated import (
    DatasetViewsGeneratedCapability,
    are_dataset_entity_views_generated,
    dataset_entity_instances,
    dataset_entity_view_plan,
    generate_dataset_entity_views,
)


class FakeContext:
    def __init__(self, **parameters: Any) -> None:
        self._parameters: Dict[str, Any] = dict(parameters)

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)


def _dataset(
    container_path: Path,
    dataset_name: str,
    entity_type: str,
    identifier: str,
) -> Path:
    facades_path = (
        container_path / ".__ontobdc__" / "view" / "facades.jsonld"
    )
    facades_path.parent.mkdir(parents=True, exist_ok=True)
    if not facades_path.exists():
        facades_path.write_text(
            json.dumps({"@context": {}, "@graph": []}),
            encoding="utf-8",
        )
    metadata_path = container_path / dataset_name / ".__ontobdc__"
    metadata_path.mkdir(parents=True)
    datapackage_path = metadata_path / "datapackage.json"
    datapackage_path.write_text(
        json.dumps(
            {
                "dataEntity": {
                    "id": f"urn:test:{entity_type}/{identifier}",
                    "identifier": identifier,
                    "type": f"urn:test:type#{entity_type}",
                }
            }
        ),
        encoding="utf-8",
    )
    return datapackage_path


def _template(
    container_path: Path,
    entity_directory: str,
    content: str,
) -> Path:
    template_names = {
        "work_stream": "work_stream.html.jinja",
        "ifc_work_schedule": "ifc_work_schedule.html.jinja",
    }
    source_path = (
        container_path
        / "template"
        / template_names[entity_directory]
    )
    source_path.parent.mkdir(parents=True)
    source_path.write_text(content, encoding="utf-8")
    return source_path


def test_generates_page_for_each_real_dataset_entity(tmp_path: Path) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    _dataset(container_path, ".workstream", "WorkStream", "workstream-a")
    _dataset(container_path, "desmobilizacao", "WorkStream", "workstream-b")
    _dataset(
        container_path,
        "cronograma",
        "IfcWorkSchedule",
        "schedule-a",
    )
    _template(
        container_path,
        "work_stream",
        "<html>{{ entity_id }} {{ identifier }}"
        "<script>{{ facades_jsonld | safe }}</script></html>\n",
    )
    _template(
        container_path,
        "ifc_work_schedule",
        "<html>{{ entity_id }} {{ identifier }}</html>\n",
    )

    result = generate_dataset_entity_views(container_path)

    assert [item["identifier"] for item in dataset_entity_instances(container_path)] == [
        "workstream-a",
        "schedule-a",
        "workstream-b",
    ]
    assert result["page_count"] == 3
    assert (
        container_path / "view/work_stream/workstream-a.html"
    ).is_file()
    second_workstream = (
        container_path / "view/work_stream/workstream-b.html"
    )
    assert second_workstream.is_file()
    assert "workstream-b" in second_workstream.read_text(encoding="utf-8")
    assert "workstream-a" not in second_workstream.read_text(encoding="utf-8")
    assert '"@graph":[]' in second_workstream.read_text(encoding="utf-8")
    assert (
        container_path / "view/ifc_work_schedule/schedule-a.html"
    ).is_file()

    context = FakeContext(container_path=str(container_path))
    assert are_dataset_entity_views_generated(context)


def test_new_instance_invalidates_generated_state(tmp_path: Path) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    _dataset(container_path, "first", "WorkStream", "first-id")
    _template(
        container_path,
        "work_stream",
        "{{ identifier }}",
    )
    context = FakeContext(container_path=str(container_path))

    generate_dataset_entity_views(container_path)
    assert are_dataset_entity_views_generated(context)

    _dataset(container_path, "second", "WorkStream", "second-id")
    assert not are_dataset_entity_views_generated(context)


def test_missing_entity_template_is_not_satisfied(tmp_path: Path) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    _dataset(container_path, "dataset", "IfcWorkSchedule", "schedule-id")
    context = FakeContext(container_path=str(container_path))

    assert not are_dataset_entity_views_generated(context)
    with pytest.raises(ValueError, match="view template not found"):
        dataset_entity_view_plan(container_path)


def test_ignores_other_dataset_entities(tmp_path: Path) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    _dataset(container_path, "dataset", "OtherEntity", "instance-id")

    result = generate_dataset_entity_views(container_path)

    assert result["page_count"] == 0
    assert not (container_path / "view").exists()


def test_capability_requires_facades_serialized(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    context = FakeContext(container_path=str(container_path))
    monkeypatch.setattr(
        "ontobdc.view.plugin.capability.dataset_views_generated."
        "FacadesSerializedCapability.is_satisfied",
        lambda _self, _context: False,
    )

    assert not DatasetViewsGeneratedCapability().is_satisfied(context)


def test_capability_reaches_dataset_views_generated_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    _dataset(container_path, "dataset", "WorkStream", "instance-id")
    _template(
        container_path,
        "work_stream",
        "{{ identifier }}",
    )
    context = FakeContext(container_path=str(container_path))
    monkeypatch.setattr(
        "ontobdc.view.plugin.capability.dataset_views_generated."
        "FacadesSerializedCapability.is_satisfied",
        lambda _self, _context: True,
    )

    result = DatasetViewsGeneratedCapability().execute(context)

    assert (
        result["resulting_state"]
        == ContainerViewProcessState.DATASET_VIEWS_GENERATED
    )
    assert result["page_count"] == 1
