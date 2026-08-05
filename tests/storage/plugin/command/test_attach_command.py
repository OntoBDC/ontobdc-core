from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

from ontobdc.storage.plugin.command.container.attach import StorageAttachCommand


class FakeContext:
    def __init__(self) -> None:
        self._parameters: Dict[str, Any] = {}

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def delete_parameter(self, name: str) -> None:
        self._parameters.pop(name, None)


def test_attach_command_matches_exact_contract() -> None:
    assert StorageAttachCommand.accepts(
        ["storage", "--container-path", "container", "--attach"]
    )
    assert not StorageAttachCommand.accepts(
        ["storage", "--container", "container", "--attach"]
    )
    assert not StorageAttachCommand.accepts(
        ["storage", "--attach", "--container-path", "container"]
    )


def test_attach_command_binds_container_path(tmp_path: Path) -> None:
    container_path = tmp_path / "container"
    container_path.mkdir()
    context = FakeContext()
    request = SimpleNamespace(
        command_args=["--container-path", str(container_path), "--attach"],
        context=context,
    )

    command = StorageAttachCommand(request)

    assert command.check()
    assert Path(context.get_parameter_value("container_path")) == (
        container_path.resolve()
    )
