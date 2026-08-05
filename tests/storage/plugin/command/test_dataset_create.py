from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.storage.plugin.command.dataset.create import DatasetCreateCommand
from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy


class FakeContext:
    def __init__(self, raw_args: List[str], **parameters: Any) -> None:
        self.raw_args = raw_args
        self._parameters: Dict[str, Any] = dict(parameters)

    @property
    def root_path(self) -> str:
        return str(Path.cwd())

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def delete_parameter(self, name: str) -> None:
        self._parameters.pop(name, None)

    def has_parameter(self, name: str) -> bool:
        return name in self._parameters


def _request(context: FakeContext, arguments: List[str]) -> CliCommandRequest:
    return CliCommandRequest(
        logical_component="storage",
        component_action="ds_create",
        command_args=arguments,
        context=context,
    )


def test_accepts_generic_container_selector() -> None:
    assert DatasetCreateCommand.accepts(
        [
            "storage",
            "--container",
            "urn:container",
            "--create",
            "cronograma",
        ]
    )


def test_resolves_generic_container_selector_through_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container_path = tmp_path / "techcenter-doc"
    container_path.mkdir()
    container_id = "urn:ontobdc:storage/local/techcenter-doc"
    arguments = [
        "--container",
        container_id,
        "--create",
        "cronograma",
    ]
    context = FakeContext(raw_args=arguments)

    monkeypatch.setattr(
        ContainerIdStrategy,
        "_registered_containers",
        staticmethod(lambda _root_path=None: ((container_id, container_path),)),
    )

    command = DatasetCreateCommand(_request(context, arguments))

    assert command.check()
    assert context.get_parameter_value("container_id") == container_id
    assert Path(context.get_parameter_value("container_path")) == container_path
    assert Path(context.get_parameter_value("dataset_path")) == (
        container_path / "cronograma"
    )


def test_preserves_explicit_container_id_selector(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container_path = tmp_path / "techcenter-doc"
    container_path.mkdir()
    container_id = "urn:ontobdc:storage/local/techcenter-doc"
    arguments = [
        "--container-id",
        container_id,
        "--create",
        "cronograma",
    ]
    context = FakeContext(raw_args=arguments)

    monkeypatch.setattr(
        ContainerIdStrategy,
        "_registered_containers",
        staticmethod(lambda _root_path=None: ((container_id, container_path),)),
    )

    command = DatasetCreateCommand(_request(context, arguments))

    assert command.check()
    assert context.get_parameter_value("container_id") == container_id
    assert Path(context.get_parameter_value("dataset_path")) == (
        container_path / "cronograma"
    )
