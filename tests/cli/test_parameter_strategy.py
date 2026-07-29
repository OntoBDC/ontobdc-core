from types import SimpleNamespace

from ontobdc.cli import _check_command
from ontobdc.shared.domain.model.parameter import ParameterMetadata


class _Context:
    def __init__(self) -> None:
        self.values = {}

    def get_parameter_value(self, key):
        return self.values.get(key)

    def set_parameter_value(self, key, value) -> None:
        self.values[key] = value


class _ProjectStrategy:
    METADATA = ParameterMetadata(
        id="test.project",
        version="1.0.0",
        name="project",
        description="Normalize the project alias.",
        author=["test"],
        python_type=str,
    )

    def execute(self, context):
        context.set_parameter_value(
            "project_id",
            context.get_parameter_value("project"),
        )
        return context


class _ParameterLoader:
    def get_all(self):
        return [_ProjectStrategy()]


class _Command:
    METADATA = SimpleNamespace(
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
            }
        ]
    )

    def __init__(self) -> None:
        self._request = SimpleNamespace(context=_Context())

    def check(self) -> bool:
        return self._request.context.get_parameter_value("project_id") == "project-123"


def test_check_command_applies_injected_parameter_strategy() -> None:
    command = _Command()

    result = _check_command(
        command,
        ["--project", "project-123"],
        logger=object(),
        parameter_loader=_ParameterLoader(),
    )

    assert result is True
    assert command._request.context.get_parameter_value("project_id") == "project-123"
