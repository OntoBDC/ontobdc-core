from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import patch

from ontobdc.storage.plugin.command.container.update import StorageUpdateCommand


class FakeContext:
    def __init__(self, container_id: Optional[str]) -> None:
        self.root_path: str = str(Path.cwd())
        self._parameters: Dict[str, Any] = {}
        if container_id is not None:
            self._parameters["container_id"] = container_id

    def get_parameter_value(self, parameter_name: str) -> Optional[Any]:
        return self._parameters.get(parameter_name)

    def set_parameter_value(
        self,
        parameter_name: str,
        parameter_value: Any,
    ) -> None:
        self._parameters[parameter_name] = parameter_value

    def delete_parameter(self, parameter_name: str) -> None:
        self._parameters.pop(parameter_name, None)


def test_update_command_accepts_current_container_form() -> None:
    assert StorageUpdateCommand.accepts(["storage", "--update"])


def test_update_command_declares_container_id_parameter() -> None:
    valued_parameter_names = {
        accepted_flag[2:].replace("-", "_")
        for argument in StorageUpdateCommand.METADATA.arguments
        if argument.get("valued")
        for accepted_flag in argument.get("accepts", [])
        if accepted_flag.startswith("--")
    }

    assert "container_id" in valued_parameter_names


def test_update_command_uses_resolved_current_container() -> None:
    container_id = "urn:ontobdc:storage/local/example"
    container_path = Path.cwd() / "example"
    context = FakeContext(container_id)
    request = SimpleNamespace(
        command_args=["--update"],
        context=context,
    )
    command = StorageUpdateCommand(request)

    with patch.object(
        command,
        "_resolve_registered_container",
        return_value=(container_id, container_path),
    ) as resolver:
        assert command.check()

    resolver.assert_called_once_with(container_id)
    assert context.get_parameter_value("container_id") == container_id
    assert context.get_parameter_value("container_path") == str(container_path)


def test_update_command_preserves_legacy_explicit_container_flag() -> None:
    container_id = "urn:ontobdc:storage/local/example"
    container_path = Path.cwd() / "example"
    context = FakeContext(None)
    request = SimpleNamespace(
        command_args=["--container", "example", "--update"],
        context=context,
    )
    command = StorageUpdateCommand(request)

    with patch.object(
        command,
        "_resolve_registered_container",
        return_value=(container_id, container_path),
    ):
        assert command.check()

    assert context.get_parameter_value("container_id") == container_id
    assert context.get_parameter_value("container_path") == str(container_path)
