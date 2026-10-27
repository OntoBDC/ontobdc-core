"""The default and explicit repositories of ontobdc ddock --install."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ontobdc.cli import CliParameterValidationOrchestrator
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.ddock.plugin.command.install import DdockInstallCommand
from ontobdc.ddock.plugin.parameter.install_from_github import InstallFromGitHubStrategy


DEFAULT = "https://github.com/OntoBDC/ontobdc-ddock"
DEFAULT_ZIP = "https://github.com/OntoBDC/ontobdc-ddock/archive/refs/heads/master.zip"
CUSTOM = "https://github.com/example/custom-ddock"
CUSTOM_ZIP = "https://github.com/example/custom-ddock/archive/refs/heads/main.zip"


def context_for(args: list[str], initial: dict[str, str] | None = None):
    values = dict(initial or {})
    context = Mock(spec=CliContextPort)
    context.raw_args = args
    context.get_parameter_value.side_effect = values.get
    context.set_parameter_value.side_effect = values.__setitem__
    context.delete_parameter.side_effect = lambda name: values.pop(name, None)
    return context, values


def command_for(args: list[str], context: CliContextPort) -> DdockInstallCommand:
    command = DdockInstallCommand.__new__(DdockInstallCommand)
    command._request = SimpleNamespace(command_args=args, context=context)
    return command


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["ddock", "--install"], True),
        (["ddock", "--install", CUSTOM], True),
        (["ddock"], False),
        (["ddock", "--install", ""], False),
        (["ddock", "--install", "--other"], False),
        (["ddock", "--install", CUSTOM, "extra"], False),
    ],
)
def test_install_command_accepts_an_optional_repository(args: list[str], expected: bool) -> None:
    assert DdockInstallCommand.accepts(args) is expected


def test_install_without_repository_uses_official_ddock_not_a_saved_source() -> None:
    context, values = context_for(
        ["--install"],
        {"ddock_install_source": CUSTOM, "ddock_install_zip": CUSTOM_ZIP},
    )
    with patch.object(GitHubZipAddress, "resolve", return_value=DEFAULT_ZIP) as resolve:
        assert InstallFromGitHubStrategy().execute(context) is context

    resolve.assert_called_once_with(DEFAULT)
    assert values["ddock_install_source"] == DEFAULT
    assert values["ddock_install_zip"] == DEFAULT_ZIP
    assert command_for(["--install"], context).check()


def test_explicit_repository_takes_precedence() -> None:
    context, values = context_for(["--install", CUSTOM])
    with patch.object(GitHubZipAddress, "resolve", return_value=CUSTOM_ZIP) as resolve:
        InstallFromGitHubStrategy().execute(context)

    resolve.assert_called_once_with(CUSTOM)
    assert values["ddock_install_source"] == CUSTOM
    assert values["ddock_install_zip"] == CUSTOM_ZIP
    assert command_for(["--install", CUSTOM], context).check()


def test_unresolvable_repository_is_not_replaced_by_default() -> None:
    context, values = context_for(
        ["--install", CUSTOM], {"ddock_install_zip": DEFAULT_ZIP},
    )
    with patch.object(GitHubZipAddress, "resolve", return_value=None) as resolve:
        InstallFromGitHubStrategy().execute(context)

    resolve.assert_called_once_with(CUSTOM)
    assert "ddock_install_zip" not in values
    assert not command_for(["--install", CUSTOM], context).check()


def test_strategy_does_not_run_for_other_commands() -> None:
    context, values = context_for(["--help"], {"ddock_install_zip": "keep"})
    with patch.object(GitHubZipAddress, "resolve") as resolve:
        InstallFromGitHubStrategy().execute(context)
    resolve.assert_not_called()
    assert values["ddock_install_zip"] == "keep"


def test_implicit_default_passes_cli_parameter_validation() -> None:
    context, values = context_for(["--install"])
    command = command_for(["--install"], context)
    loader = SimpleNamespace(
        get_all=lambda: [InstallFromGitHubStrategy()],
        root_packages=("ontobdc",),
    )
    with patch.object(GitHubZipAddress, "resolve", return_value=DEFAULT_ZIP):
        assert CliParameterValidationOrchestrator().check(
            command,
            ["ddock", "--install"],
            NullLogRepository(),
            parameter_loader=loader,
        )
    assert values["ddock_install_zip"] == DEFAULT_ZIP
