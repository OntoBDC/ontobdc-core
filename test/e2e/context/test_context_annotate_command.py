"""
Coverage for the `AnnotateCommand` declared in
``ontobdc.context.plugin.command.annotate``.

This command class is not registered by the installed CLI loader (its
``logical_component`` is ``annotate`` while it lives under the ``context``
plugin tree), so the installed executable never routes ``annotate
--container <id> --file <id>`` to it. The tests below document that routing
behaviour and exercise the command's own routing/check/run logic directly so
the source file is meaningfully covered.
"""

from typing import Dict, List, Tuple
from unittest.mock import Mock

import pytest

from ontobdc.context.plugin.command.annotate import AnnotateCommand
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


def _make_request(command_args: List[str], values: Dict[str, str]) -> CliCommandRequest:
    """Build a request backed by an in-memory mock context."""
    context: CliContextPort = Mock(spec=CliContextPort)
    context.get_parameter_value.side_effect = lambda name: values.get(name)
    context.set_parameter_value.side_effect = lambda name, value: values.__setitem__(name, value)
    return CliCommandRequest(
        logical_component="annotate",
        component_action="annotate",
        command_args=command_args,
        context=context,
    )


class TestOntobdcContextAnnotateCommandRouting:
    """
    The installed CLI does not route ``annotate --container <id> --file <id>``
    because the command is not registered under either component.
    """

    @pytest.mark.parametrize(
        "args",
        [
            ("--container", "urn:uuid:00000000-0000-4000-8000-000000000000", "--file", "file.txt"),
            ("--file", "file.txt", "--container", "urn:uuid:00000000-0000-4000-8000-000000000000"),
        ],
    )
    def test_container_file_route_is_not_registered(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("annotate", *args)
        assert result.exit_code != 0, result.stdout
        assert "Annotation Not Available" not in result.stdout
        assert "Invalid command arguments" in result.stdout


class TestContextAnnotateCommandClass:
    """Direct coverage of ``AnnotateCommand`` routing, check and run logic."""

    def test_metadata_declares_container_and_file_flags(self) -> None:
        metadata: CliCommandMetadata = AnnotateCommand.METADATA
        accepts: List[str] = [
            flag
            for argument in metadata.arguments
            for flag in argument["accepts"]
        ]
        assert "--container" in accepts
        assert "--file" in accepts

    @pytest.mark.parametrize(
        "args",
        [
            [],
            ["--container"],
            ["--file"],
            ["--container", "urn:uuid:00000000-0000-4000-8000-000000000000"],
            ["--file", "file.txt"],
            ["--container", "", "--file", "file.txt"],
            ["--container", "urn:uuid:00000000-0000-4000-8000-000000000000", "--file", "file.txt", "--extra", "x"],
        ],
    )
    def test_accepts_rejects_incomplete_or_invalid_routes(
        self, args: List[str]
    ) -> None:
        assert AnnotateCommand.accepts(["annotate", *args]) is False

    @pytest.mark.parametrize(
        "args",
        [
            ["--container", "urn:uuid:00000000-0000-4000-8000-000000000000", "--file", "file.txt"],
            ["--file", "file.txt", "--container", "urn:uuid:00000000-0000-4000-8000-000000000000"],
        ],
    )
    def test_accepts_matches_valid_container_file_routes(
        self, args: List[str]
    ) -> None:
        assert AnnotateCommand.accepts(["annotate", *args]) is True

    @pytest.mark.parametrize(
        "command_args",
        [
            ["--container", "urn:uuid:00000000-0000-4000-8000-000000000000", "--file", "file.txt"],
            ["--file", "file.txt", "--container", "urn:uuid:00000000-0000-4000-8000-000000000000"],
        ],
    )
    def test_check_passes_for_valid_routes(
        self, command_args: List[str]
    ) -> None:
        request: CliCommandRequest = _make_request(command_args, {})
        command: AnnotateCommand = AnnotateCommand(request)
        assert command.check() is True

    def test_run_reports_annotation_pipeline_not_restored(self) -> None:
        values: Dict[str, str] = {
            "container_id": "urn:uuid:00000000-0000-4000-8000-000000000000",
            "file_id": "file-global-id",
            "file_path": "file.txt",
        }
        request: CliCommandRequest = _make_request(
            [
                "--container",
                "urn:uuid:00000000-0000-4000-8000-000000000000",
                "--file",
                "file.txt",
            ],
            values,
        )
        command: AnnotateCommand = AnnotateCommand(request)
        response = command.run()

        assert response.title == "Annotation Not Available"
        assert "annotation pipeline has not been restored" in response.description

    def test_run_raises_when_container_parameter_unresolved(self) -> None:
        request: CliCommandRequest = _make_request(
            [
                "--container",
                "urn:uuid:00000000-0000-4000-8000-000000000000",
                "--file",
                "file.txt",
            ],
            {},
        )
        command: AnnotateCommand = AnnotateCommand(request)
        with pytest.raises(Exception):
            command.run()
