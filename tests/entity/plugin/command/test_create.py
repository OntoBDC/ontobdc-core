import json
from pathlib import Path

import pytest

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.entity.plugin.command.create import EntityCreateCommand


class _Context(CliContextPort):
    def __init__(self, root_path: Path) -> None:
        self._root_path = str(root_path)
        self._values = {}

    @property
    def raw_args(self):
        return []

    @property
    def unprocessed_args(self):
        return []

    @property
    def is_capability_targeted(self):
        return False

    @property
    def target_capability_id(self):
        return None

    @property
    def root_path(self):
        return self._root_path

    @property
    def language(self):
        return "en"

    def has_parameter(self, param_key):
        return param_key in self._values

    def get_parameter_value(self, param_key):
        return self._values.get(param_key)

    def set_parameter_value(self, param_key, param_value):
        self._values[param_key] = param_value

    def delete_parameter(self, param_key):
        self._values.pop(param_key, None)

    def clear_parameters(self, param_keys):
        for param_key in param_keys:
            self.delete_parameter(param_key)

    def reload(self):
        return None


def _make_command(tmp_path: Path, container_path: Path) -> EntityCreateCommand:
    context = _Context(tmp_path)
    context.set_parameter_value("container_id", "urn:ontobdc:container:test")
    context.set_parameter_value("entity", "WorkStream")
    context.set_parameter_value(
        "create",
        "Cabeamento de Lógica e Instrumentação",
    )
    request = CliCommandRequest(
        logical_component="entity",
        component_action="entity_create",
        command_args=[
            "--container-id",
            "urn:ontobdc:container:test",
            "--entity",
            "WorkStream",
            "--create",
            "Cabeamento de Lógica e Instrumentação",
        ],
        context=context,
    )
    return EntityCreateCommand(request)


def test_accepts_explicit_or_inferred_container() -> None:
    assert EntityCreateCommand.accepts(
        [
            "entity",
            "--container-id",
            "urn:ontobdc:container:test",
            "--entity",
            "WorkStream",
            "--create",
            "Cabeamento lógico",
        ]
    )
    assert EntityCreateCommand.accepts(
        [
            "entity",
            "--entity",
            "WorkStream",
            "--create",
            "Cabeamento lógico",
        ]
    )


def test_creates_and_reuses_workstream_workbook(
    tmp_path,
    monkeypatch,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("frictionless")
    container_path = tmp_path / "container"
    (container_path / ".__ontobdc__").mkdir(parents=True)
    (container_path / ".__ontobdc__" / "datapackage.json").write_text(
        json.dumps({"name": "test", "resources": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        EntityCreateCommand,
        "_get_registered_container_location",
        lambda self, container_id, root_path: container_path,
    )
    command = _make_command(tmp_path, container_path)

    assert command.check()
    first_response = command.run()
    second_response = command.run()

    workbook_path = Path(first_response.content["workbook_path"])
    assert workbook_path == (
        container_path / "payload" / "document" / "workstreams.xlsx"
    )
    assert second_response.content["work_stream_count"] == 1
    workbook = openpyxl.load_workbook(workbook_path)
    worksheet = workbook["WorkStream"]
    assert worksheet.max_row == 2
    assert worksheet["C2"].value == "Cabeamento de Lógica e Instrumentação"
    workbook.close()
